resource "aws_security_group" "emr_serverless" {
  name        = "${var.name_prefix}-emr-serverless-sg"
  description = "Security group for EMR Serverless jobs."
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-emr-serverless-sg"
  }
}

resource "aws_emrserverless_application" "spark" {
  name          = "${var.name_prefix}-spark"
  release_label = var.release_label
  type          = "SPARK"

  network_configuration {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.emr_serverless.id]
  }

  initial_capacity {
    initial_capacity_type = "Driver"

    initial_capacity_config {
      worker_count = 1

      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
        disk   = "20 GB"
      }
    }
  }

  initial_capacity {
    initial_capacity_type = "Executor"

    initial_capacity_config {
      worker_count = 1

      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
        disk   = "20 GB"
      }
    }
  }

  maximum_capacity {
    cpu    = var.maximum_cpu
    memory = var.maximum_memory
    disk   = var.maximum_disk
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = var.idle_timeout_minutes
  }
}
