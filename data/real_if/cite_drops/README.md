# Cite drops (gitignored bytes)

Official PDF / KMZ / KML cites go to:

```
data/real_if/<fire_id>/cite/
```

via:

```powershell
python scripts/copy_cite_to_real_if.py --cite PATH --fire-id hellin_2024
```

Missing `--cite` / missing file / unknown `--fire-id` → exit **1**.

**Never commit cite bytes.** Copy ≠ promote. Promote still requires H1–H7 + Alonso in the same PR.
