# Relator → Cloud Run. No Vertex / Gemini.
# Requires: gcloud auth login && gcloud auth application-default login
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

if (-not $env:GOOGLE_CLOUD_PROJECT) {
  throw "Set GOOGLE_CLOUD_PROJECT before deploying Relator."
}
$Project = $env:GOOGLE_CLOUD_PROJECT
$Region = if ($env:GOOGLE_CLOUD_REGION) { $env:GOOGLE_CLOUD_REGION } else { "europe-west1" }
$Bucket = if ($env:RELATOR_BUCKET) { $env:RELATOR_BUCKET } else { "relator-sky-$Project" }
$Service = "relator"

Write-Host "project=$Project region=$Region bucket=$Bucket (no LLM APIs)"

gcloud config set project $Project
gcloud services enable run.googleapis.com storage.googleapis.com pubsub.googleapis.com earthengine.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com --project $Project

gsutil mb -p $Project -l $Region "gs://$Bucket" 2>$null
gcloud pubsub topics create relator-source-arrived --project $Project 2>$null
gcloud artifacts repositories create relator --repository-format=docker --location $Region --project $Project 2>$null

gcloud builds submit $Root --config hackathon/relator/cloudbuild.yaml --project $Project
$Image = "${Region}-docker.pkg.dev/${Project}/relator/relator:latest"

gcloud run deploy $Service `
  --image $Image `
  --project $Project `
  --region $Region `
  --allow-unauthenticated `
  --startup-probe="" `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$Project,GOOGLE_CLOUD_REGION=$Region,RELATOR_BUCKET=$Bucket" `
  --min-instances 0 `
  --max-instances 2 `
  --memory 512Mi `
  --cpu 1 `
  --timeout 180

Write-Host "done. Turn it off after the demo: gcloud run services delete $Service --region $Region --project $Project"
