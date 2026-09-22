resource "google_compute_network" "sandbox" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "sandbox" {
  name          = "${var.name_prefix}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.sandbox.id
}

resource "google_compute_firewall" "allow_internal" {
  name    = "${var.name_prefix}-internal"
  network = google_compute_network.sandbox.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
  target_tags   = ["clould-cost-sandbox"]
}

resource "google_compute_instance" "sandbox" {
  count        = var.create_compute ? 1 : 0
  name         = "${var.name_prefix}-vm"
  machine_type = "e2-micro"
  zone         = var.zone
  tags         = ["clould-cost-sandbox"]
  labels       = var.labels

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.sandbox.id
  }
}