# TO DO LIST

- [ ] Authenticate with Google Cloud:
    - Run `gcloud auth login`
    - Run `gcloud auth application-default login`
- [ ] Update Project ID:
    - Open `deployment/terraform/single-project/vars/env.tfvars`
    - Replace `your-gcp-project-id` with your actual Google Cloud Project ID.
- [ ] Deploy Infrastructure:
    - Navigate to `deployment/terraform/single-project/`
    - Run `terraform apply -var-file=vars/env.tfvars`
