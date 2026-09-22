output "network_id" { value = google_compute_network.sandbox.id }
output "subnetwork_id" { value = google_compute_subnetwork.sandbox.id }
output "instance_id" { value = try(google_compute_instance.sandbox[0].instance_id, null) }
