#!/usr/bin/env python3
"""Autonomous Wildfire Segmentation Research Pipeline v17.

Production-grade, fully autonomous ML research system for 16h unattended execution.

Solves bottlenecks: extreme imbalance (99% bg), noisy channels, copy-baseline dominance, leakage.

Phases:
  0: Data + feature analysis (10 min)
  1: Copy baseline (5 min)
  2: Optuna sweep (~14h, ~30 trials)
  3: Full retraining (45 min)
  4: Production export (30 min)
"""

import os, sys, subprocess, json, time, random, hashlib, argparse, warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict
warnings.filterwarnings("ignore")
import numpy as np

parser = argparse.ArgumentParser(description="Autonomous Wildfire Research v17")
parser.add_argument("--max-hours", type=float, default=16.0)
parser.add_argument("--n-trials", type=int, default=40)
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz")
parser.add_argument("--output-dir", type=str, default="../")
parser.add_argument("--seed", type=int, default=42)
args, _ = parser.parse_known_args()

START_TIME = time.time()
DEADLINE = START_TIME + args.max_hours * 3600
SWEEP_DEADLINE = START_TIME + (args.max_hours - 0.5) * 3600

print("=" * 80)
print("AUTONOMOUS WILDFIRE SEGMENTATION RESEARCH PIPELINE v17")
print("=" * 80)
random.seed(args.seed); np.random.seed(args.seed)

def _check_gpu():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0: print(f"  GPU: {r.stdout.strip()}")
    except: pass
_check_gpu()

# FIX: P100 sm_60 compatibility — detect BEFORE importing torch
def _install_pt_for_p100():
    try:
        r = subprocess.run(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode==0 and "P100" in r.stdout:
            print("  P100 detected — installing PyTorch 2.1.2 (supports sm_60)...")
            subprocess.run([sys.executable,"-m","pip","install","-q","torch==2.1.2","torchvision==0.16.2"],
                          check=True, capture_output=True)
            print("  PyTorch 2.1.2 installed.")
    except Exception: pass
_install_pt_for_p100()

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

torch.manual_seed(args.seed)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = DEVICE.type == "cuda"
print(f"PyTorch {torch.__version__} | Device: {DEVICE}")

try:
    import optuna
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "optuna"], check=True)
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

if not Path("WildfireFrontDynamics").exists():
    subprocess.run(["git", "clone", "--depth", "1",
                     "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"], check=True)
if Path("WildfireFrontDynamics").exists():
    os.chdir("WildfireFrontDynamics"); sys.path.insert(0, os.getcwd())

data_root = Path(args.data_dir)
if not all((data_root / s).exists() for s in ["train", "val", "test"]):
    for split in ["train", "val", "test"]:
        subprocess.run([sys.executable, "kaggle_job/preprocess_ndws.py",
                         "--split", split, "--patch-size", "64"], check=True)

# === SOTA LOSSES ===
class FocalLoss(nn.Module):
    def __init__(self, alpha=0.75, gamma=2.0, pos_weight=5.0):
        super().__init__(); self.alpha=alpha; self.gamma=gamma; self.pos_weight=pos_weight
    def forward(self, logits, targets):
        logits = torch.clamp(logits, -10, 10)
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none",
              pos_weight=torch.tensor(self.pos_weight, device=logits.device))
        p = torch.sigmoid(logits)
        p_t = p * targets + (1 - p) * (1 - targets)
        return (self.alpha * ((1 - p_t) ** self.gamma) * bce).mean()

class TverskyLoss(nn.Module):
    def __init__(self, alpha=0.3, beta=0.7, smooth=1e-7):
        super().__init__(); self.alpha=alpha; self.beta=beta; self.smooth=smooth
    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        tp = (probs * targets).sum(dim=[1,2,3])
        fp = ((1-targets) * probs).sum(dim=[1,2,3])
        fn = (targets * (1-probs)).sum(dim=[1,2,3])
        tv = (tp + self.smooth) / (tp + self.alpha*fp + self.beta*fn + self.smooth)
        return (1 - tv).mean()

class LovaszHingeLoss(nn.Module):
    @staticmethod
    def _lovasz_grad(gt_sorted):
        gts = gt_sorted.sum()
        intersection = gts - gt_sorted.float().cumsum(0)
        union = gts + (1 - gt_sorted).float().cumsum(0)
        jaccard = 1.0 - intersection / union
        if jaccard.numel() > 1: jaccard[1:] = jaccard[1:] - jaccard[:-1]
        return jaccard
    def forward(self, logits, targets):
        logits = logits.flatten(1); targets = targets.flatten(1)
        signs = 2.0 * targets - 1.0
        errors = (1.0 - logits * signs)
        errors_sorted, perm = torch.sort(errors, dim=1, descending=True)
        gt_sorted = targets.gather(1, perm)
        grad = self._lovasz_grad(gt_sorted)
        return torch.dot(F.relu(errors_sorted.reshape(-1)), grad.reshape(-1)) / logits.size(0)

class CompositeSOTALLoss(nn.Module):
    def __init__(self, w_focal=1.0, w_tversky=0.5, w_lovasz=0.3, w_bce=0.5, pos_weight=5.0, gamma=2.0):
        super().__init__()
        self.focal=FocalLoss(0.75, gamma, pos_weight); self.tversky=TverskyLoss()
        self.lovasz=LovaszHingeLoss()
        self.w_focal=w_focal; self.w_tversky=w_tversky; self.w_lovasz=w_lovasz; self.w_bce=w_bce
        self.pos_weight=pos_weight
    def forward(self, logits, targets):
        pw = torch.tensor(self.pos_weight, device=logits.device)
        bce = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pw)
        return (self.w_focal*self.focal(logits,targets) + self.w_tversky*self.tversky(logits,targets) +
                self.w_lovasz*self.lovasz(logits,targets) + self.w_bce*bce)

# === ATTENTION ===
class SEBlock(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.sq = nn.AdaptiveAvgPool2d(1)
        self.ex = nn.Sequential(nn.Linear(ch, max(ch//r,4), bias=False), nn.ReLU(inplace=True),
                                nn.Linear(max(ch//r,4), ch, bias=False), nn.Sigmoid())
    def forward(self, x):
        b,c = x.shape[:2]; s = self.ex(self.sq(x).view(b,c)).view(b,c,1,1); return x*s

class CBAM(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.avg=nn.AdaptiveAvgPool2d(1); self.max=nn.AdaptiveMaxPool2d(1)
        self.mlp=nn.Sequential(nn.Conv2d(ch,max(ch//r,4),1,bias=False),nn.ReLU(inplace=True),
                               nn.Conv2d(max(ch//r,4),ch,1,bias=False))
        self.spatial=nn.Conv2d(2,1,7,padding=3,bias=False)
    def forward(self, x):
        ca = torch.sigmoid(self.mlp(self.avg(x)) + self.mlp(self.max(x))); x = x*ca
        sa = torch.sigmoid(self.spatial(torch.cat([x.mean(1,keepdim=True), x.max(1,keepdim=True)[0]], dim=1)))
        return x*sa

# === RESIDUAL DELTA U-NET ===
class DoubleConv(nn.Module):
    def __init__(self, i, o, m=None, norm="group", att=None):
        super().__init__(); m=m or o
        nf = lambda c: nn.GroupNorm(8,c) if norm=="group" else nn.BatchNorm2d(c)
        self.body = nn.Sequential(nn.Conv2d(i,m,3,padding=1,bias=False), nf(m), nn.ReLU(inplace=True),
                                  nn.Conv2d(m,o,3,padding=1,bias=False), nf(o), nn.ReLU(inplace=True))
        self.att = CBAM(o) if att=="cbam" else (SEBlock(o) if att=="se" else nn.Identity())
    def forward(self, x): return self.att(self.body(x))

class DownBlock(nn.Module):
    def __init__(self, i, o, **kw): super().__init__(); self.p=nn.Sequential(nn.MaxPool2d(2), DoubleConv(i,o,**kw))
    def forward(self, x): return self.p(x)

class UpBlock(nn.Module):
    def __init__(self, i, o, bil=True, **kw):
        super().__init__()
        if bil: self.up=nn.Upsample(scale_factor=2,mode="bilinear",align_corners=True); self.conv=DoubleConv(i,o,m=i//2,**kw)
        else: self.up=nn.ConvTranspose2d(i,i//2,2,2); self.conv=DoubleConv(i,o,**kw)
    def forward(self, x1, x2):
        x1=self.up(x1); dy=x2.size(2)-x1.size(2); dx=x2.size(3)-x1.size(3)
        x1=F.pad(x1,[dx//2,dx-dx//2,dy//2,dy-dy//2]); return self.conv(torch.cat([x2,x1],dim=1))

class ResidualWildfireUNet(nn.Module):
    def __init__(self, in_channels=18, base_ch=32, depth=3, bilinear=True, norm="group", attention="cbam", dropout=0.1):
        super().__init__(); kw=dict(norm=norm, attention=attention)
        self.inc=DoubleConv(in_channels, base_ch, **kw)
        self.downs=nn.ModuleList(); ch=base_ch
        for _ in range(depth): nc=min(ch*2,512); self.downs.append(DownBlock(ch,nc,**kw)); ch=nc
        self.ups=nn.ModuleList()
        for i in range(depth):
            oc=max(base_ch*(2**(depth-i-1)), base_ch); self.ups.append(UpBlock(ch,oc,bilinear,**kw)); ch=oc
        self.drop=nn.Dropout2d(dropout) if dropout>0 else nn.Identity()
        self.outc=nn.Conv2d(ch,1,1)
        self.delta_scale=nn.Parameter(torch.tensor(1.0))
        self.copy_bias=nn.Parameter(torch.tensor(2.0))
    def forward(self, x, prev_fire):
        x1=self.inc(x); skips=[x1]
        for d in self.downs: x1=d(x1); skips.append(x1)
        skips=skips[:-1][::-1]
        for u,s in zip(self.ups,skips): x1=u(x1,s)
        delta=self.outc(self.drop(x1))
        return self.delta_scale*delta + self.copy_bias*(prev_fire*2-1)
    def predict(self, x, pf): return torch.sigmoid(self.forward(x, pf))

# === DATASET ===
class WildfireDataset(Dataset):
    def __init__(self, directory, augment=False):
        self.directory=Path(directory); self.files=sorted(self.directory.glob("*.npz"))
        self.augment=augment; self._fps=self._fingerprints()
    def _fingerprints(self):
        fps=[]
        for f in self.files:
            try:
                with np.load(f) as d: fps.append(hashlib.md5(d["current_fire"].tobytes()).hexdigest()[:8])
            except: fps.append("err")
        return fps
    def __len__(self): return len(self.files)
    def __getitem__(self, idx):
        with np.load(self.files[idx]) as d:
            seq=np.where(np.isfinite(d["sequence"]), d["sequence"].astype(np.float32), 0.0)
            cf=d["current_fire"].astype(np.float32); tf=d["target_fire"].astype(np.float32)
        seq=torch.from_numpy(seq); cf=torch.from_numpy(cf); tf=torch.from_numpy(tf)
        if self.augment:
            if random.random()<0.5: seq=torch.flip(seq,dims=[-1]); cf=torch.flip(cf,dims=[-1]); tf=torch.flip(tf,dims=[-1])
            if random.random()<0.5: seq=torch.flip(seq,dims=[-2]); cf=torch.flip(cf,dims=[-2]); tf=torch.flip(tf,dims=[-2])
        return seq, cf, tf

def prepare_input(seq, cf):
    B,T,C,H,W = seq.shape; return torch.cat([seq.reshape(B,T*C,H,W), cf.unsqueeze(1)], dim=1)

def compute_iou(pred, target, thresh=0.5, eps=1e-7):
    pb=(pred>=thresh).astype(np.float64); tb=(target>=thresh).astype(np.float64)
    tp=np.sum((pb==1)&(tb==1)); fp=np.sum((pb==1)&(tb==0)); fn=np.sum((pb==0)&(tb==1))
    return tp/(tp+fp+fn+eps)

@torch.no_grad()
def evaluate_model(model, loader, device):
    model.eval(); preds50=[]; copy_ious=[]; targets_all=[]
    for seq,cf,tf in loader:
        seq=seq.to(device); cf=cf.to(device); tf=tf.to(device)
        x=prepare_input(seq,cf); tgt=tf.unsqueeze(1).float()
        logits=model(x, cf.unsqueeze(1)); probs=torch.sigmoid(logits)
        preds50.append(probs.cpu().numpy()); targets_all.append(tgt.cpu().numpy())
        cf_np=cf.unsqueeze(1).cpu().numpy(); tf_np=tgt.cpu().numpy()
        copy_ious.append(compute_iou(cf_np, tf_np, 0.5))
    preds=np.concatenate(preds50); tgts=np.concatenate(targets_all)
    return {"iou@0.5": float(compute_iou(preds,tgts,0.5)), "copy_baseline_iou": float(np.mean(copy_ious))}

def analyze_features(ds, max_n=500):
    print("\n=== FEATURE IMPORTANCE ANALYSIS ===")
    scores=defaultdict(list)
    names=["slope","aspect","temp","hum","wind_sp","wind_dir","precip","press","cloud","vis",
           "dew","veg","ERC","1-ERC","pad0","pad1","FFMC","prev_fire"]
    for i in range(min(len(ds),max_n)):
        seq,cf,tf=ds[i]; T,C,H,W=seq.shape; tf_f=(tf>=0.5).numpy().flatten().astype(int)
        for ci in range(C):
            ch=seq[0,ci].numpy().flatten()
            if np.std(ch)<1e-6: scores[ci].append(0.0); continue
            r=np.corrcoef(ch,tf_f)[0,1]; scores[ci].append(abs(r) if np.isfinite(r) else 0.0)
    ranked=sorted([(ci, names[ci] if ci<len(names) else f"ch{ci}", float(np.mean(s))) for ci,s in scores.items()], key=lambda x:x[2], reverse=True)
    for ci,n,s in ranked: print(f"  {n:12s} score={s:.4f} {'#'*int(s*200)}")
    total=sum(r[2] for r in ranked)+1e-7; cs=0; sel=[]
    for ci,n,s in ranked:
        cs+=s; sel.append(ci)
        if cs/total>0.95: break
    print(f"\n  Selected {len(sel)}/{len(ranked)} channels: {sel}")
    return sel

# === OPTUNA OBJECTIVE ===
def create_objective(train_ds, val_ds, device):
    def objective(trial):
        if time.time()>SWEEP_DEADLINE: trial.stop()
        cfg={"base_ch":trial.suggest_categorical("base_ch",[16,32,48]),
             "depth":trial.suggest_int("depth",2,4),
             "attention":trial.suggest_categorical("attention",["cbam","se","none"]),
             "norm":trial.suggest_categorical("norm",["group","batch"]),
             "dropout":trial.suggest_float("dropout",0.0,0.3),
             "lr":trial.suggest_float("lr",1e-4,5e-3,log=True),
             "batch_size":trial.suggest_categorical("batch_size",[16,32,64]),
             "w_focal":trial.suggest_float("w_focal",0.5,2.0),
             "w_tversky":trial.suggest_float("w_tversky",0.1,1.0),
             "w_lovasz":trial.suggest_float("w_lovasz",0.1,0.8),
             "w_bce":trial.suggest_float("w_bce",0.1,1.0),
             "pos_weight":trial.suggest_float("pos_weight",3.0,15.0),
             "focal_gamma":trial.suggest_float("focal_gamma",1.5,3.0),
             "epochs":trial.suggest_int("epochs",15,40)}
        att = None if cfg["attention"]=="none" else cfg["attention"]
        s_seq,_,_=train_ds[0]; in_ch=s_seq.shape[0]*s_seq.shape[1]+1
        model=ResidualWildfireUNet(in_channels=in_ch, base_ch=cfg["base_ch"], depth=cfg["depth"],
                                    norm=cfg["norm"], attention=att, dropout=cfg["dropout"]).to(device)
        trial.set_user_attr("n_params", sum(p.numel() for p in model.parameters() if p.requires_grad))
        crit=CompositeSOTALLoss(cfg["w_focal"],cfg["w_tversky"],cfg["w_lovasz"],cfg["w_bce"],cfg["pos_weight"],cfg["focal_gamma"])
        opt=torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
        sch=torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=5, T_mult=2, eta_min=1e-6)
        sc=torch.amp.GradScaler('cuda', enabled=USE_AMP)
        tl=DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True, num_workers=2, pin_memory=True, drop_last=True)
        vl=DataLoader(val_ds, batch_size=cfg["batch_size"], shuffle=False, num_workers=2, pin_memory=True)
        best_iou=0.0; no_imp=0
        for ep in range(cfg["epochs"]):
            if time.time()>SWEEP_DEADLINE: break
            model.train()
            for seq,cf,tf in tl:
                seq=seq.to(device);cf=cf.to(device);tf=tf.to(device)
                x=prepare_input(seq,cf); tgt=tf.unsqueeze(1).float()
                opt.zero_grad()
                with torch.amp.autocast('cuda', enabled=USE_AMP):
                    logits=model(x,cf.unsqueeze(1)); loss=crit(logits,tgt)
                sc.scale(loss).backward(); sc.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                sc.step(opt); sc.update()
            sch.step()
            vr=evaluate_model(model, vl, device); vi=vr.get("iou@0.5",0.0)
            trial.report(vi, ep)
            if trial.should_prune(): raise optuna.TrialPruned()
            if vi>best_iou: best_iou=vi; no_imp=0
            else:
                no_imp+=1
                if no_imp>=5: break
        trial.set_user_attr("copy_baseline_iou", vr.get("copy_baseline_iou",0.0))
        trial.set_user_attr("margin_over_copy", best_iou-vr.get("copy_baseline_iou",0.0))
        return best_iou
    return objective

# === MAIN PIPELINE ===
def main():
    OUT=Path(args.output_dir); OUT.mkdir(parents=True, exist_ok=True)
    rlog=OUT/"research_log.txt"
    def log(m):
        ts=datetime.now().strftime("%H:%M:%S"); line=f"[{ts}] {m}"; print(line)
        with open(rlog,"a") as f: f.write(line+"\n")

    log("=== PHASE 0: Data + Feature Analysis ===")
    train_ds=WildfireDataset(data_root/"train", augment=True)
    val_ds=WildfireDataset(data_root/"val", augment=False)
    test_ds=WildfireDataset(data_root/"test", augment=False)
    log(f"Dataset: train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")
    tv_ov=len(set(train_ds._fps)&set(val_ds._fps)); tt_ov=len(set(train_ds._fps)&set(test_ds._fps))
    log(f"Anti-leakage: train-val overlap={tv_ov}, train-test overlap={tt_ov}")
    assert tv_ov==0 and tt_ov==0, "DATA LEAKAGE DETECTED!"
    active_ch=analyze_features(train_ds)

    log("\n=== PHASE 1: Copy Baseline ===")
    test_loader=DataLoader(test_ds, batch_size=32, shuffle=False)
    copy_ious=[]
    for _,cf,tf in test_loader:
        copy_ious.append(compute_iou(cf.unsqueeze(1).numpy(), tf.unsqueeze(1).numpy(), 0.5))
    copy_baseline_iou=float(np.mean(copy_ious))
    log(f"Copy baseline IoU@0.5: {copy_baseline_iou:.4f}")

    log(f"\n=== PHASE 2: Optuna Sweep ===")
    study=optuna.create_study(direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_startup_trials=3, n_warmup_steps=5),
        sampler=optuna.samplers.TPESampler(seed=args.seed))
    remaining=SWEEP_DEADLINE-time.time(); log(f"Sweep budget: {remaining/3600:.1f}h")
    study.optimize(create_objective(train_ds, val_ds, DEVICE), n_trials=args.n_trials,
                   timeout=remaining, catch=(Exception,))
    log(f"Sweep done: {len(study.trials)} trials, best IoU={study.best_value:.4f}")
    best_params=study.best_params
    best_params["n_params"]=study.best_trial.user_attrs.get("n_params",0)
    best_params["copy_baseline_iou"]=study.best_trial.user_attrs.get("copy_baseline_iou",0)
    (OUT/"best_params.json").write_text(json.dumps(best_params, indent=2, default=str))

    log("\n=== PHASE 3: Full Retraining ===")
    s_seq,_,_=train_ds[0]; in_ch=s_seq.shape[0]*s_seq.shape[1]+1
    att=None if best_params["attention"]=="none" else best_params["attention"]
    bm=ResidualWildfireUNet(in_channels=in_ch, base_ch=best_params["base_ch"], depth=best_params["depth"],
                            norm=best_params["norm"], attention=att, dropout=best_params["dropout"]).to(DEVICE)
    crit=CompositeSOTALLoss(best_params["w_focal"],best_params["w_tversky"],best_params["w_lovasz"],
                            best_params["w_bce"],best_params["pos_weight"],best_params["focal_gamma"])
    opt=torch.optim.AdamW(bm.parameters(), lr=best_params["lr"], weight_decay=1e-4)
    sch=torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=5, T_mult=2, eta_min=1e-6)
    sc=torch.amp.GradScaler('cuda', enabled=USE_AMP)
    tl=DataLoader(train_ds, batch_size=best_params["batch_size"], shuffle=True, num_workers=4, pin_memory=True, drop_last=True)
    vl=DataLoader(val_ds, batch_size=best_params["batch_size"], shuffle=False, num_workers=4, pin_memory=True)
    best_val=0.0
    for ep in range(50):
        if time.time()>DEADLINE-1800: break
        bm.train(); el=0; st=0
        for seq,cf,tf in tl:
            seq=seq.to(DEVICE);cf=cf.to(DEVICE);tf=tf.to(DEVICE)
            x=prepare_input(seq,cf); tgt=tf.unsqueeze(1).float()
            opt.zero_grad()
            with torch.amp.autocast('cuda',enabled=USE_AMP):
                logits=bm(x,cf.unsqueeze(1)); loss=crit(logits,tgt)
            sc.scale(loss).backward(); sc.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(bm.parameters(),1.0); sc.step(opt); sc.update()
            el+=loss.item(); st+=1
        sch.step(); vr=evaluate_model(bm,vl,DEVICE); vi=vr.get("iou@0.5",0.0)
        log(f"  Epoch {ep+1}: loss={el/st:.4f} val_iou={vi:.4f}")
        if vi>best_val: best_val=vi; torch.save(bm.state_dict(), OUT/"best_model.pt")

    log("\n=== PHASE 4: Production Export ===")
    bm.load_state_dict(torch.load(OUT/"best_model.pt", map_location=DEVICE))
    test_res=evaluate_model(bm, test_loader, DEVICE); model_iou=test_res.get("iou@0.5",0.0)
    log(f"\n=== FINAL RESULTS ===")
    log(f"Model IoU: {model_iou:.4f} | Copy baseline: {copy_baseline_iou:.4f} | Margin: {model_iou-copy_baseline_iou:+.4f}")
    try:
        scripted=torch.jit.script(bm); scripted.save(str(OUT/"wildfire_model_production.pt"))
        log("TorchScript exported")
    except Exception as e:
        log(f"TorchScript failed ({e}), saving state_dict")
        torch.save(bm.state_dict(), OUT/"wildfire_model_production.pt")
    summary={"version":"v17","pipeline":"autonomous_research","timestamp":datetime.now().isoformat(),
             "total_runtime_s":time.time()-START_TIME,"n_trials":len(study.trials),"best_sweep_iou":study.best_value,
             "copy_baseline_iou":copy_baseline_iou,"final_model_iou":model_iou,
             "margin_over_copy":model_iou-copy_baseline_iou,"best_params":best_params,
             "test_metrics":test_res,"beats_copy_baseline":model_iou>copy_baseline_iou}
    (OUT/"final_report.json").write_text(json.dumps(summary, indent=2, default=str))
    log(f"\n=== PIPELINE COMPLETE ({(time.time()-START_TIME)/3600:.1f}h) ===")
    log(f"Beats copy baseline: {'YES' if summary['beats_copy_baseline'] else 'NO'}")
    return summary

if __name__=="__main__": main()