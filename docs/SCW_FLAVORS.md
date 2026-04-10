# Scaleway Flavors presentation

## 3rd generation

The instance types BASIC3-X, COMPUTE3-X, and STANDARD3-X are part of Scaleway's Instance ranges, each designed for specific use cases and performance requirements. Here are the key differences between them:

- BASIC3-X (Development Instances)
  - Use Case: Ideal for lightweight workloads such as development, testing, personal projects, and low-traffic websites.
  - vCPU: Shared vCPUs (AMD EPYC™), meaning physical cores are shared among multiple instances.
  - Performance: Cost-effective but with variable performance depending on host load (potential for "noisy neighbors").
  - Memory: Ranges from 2 GiB to 128 GiB.
  - Storage: Supports both Local and Resilient Block Storage.
  - Bandwidth: Up to 10 Gbps.
  - Best For: Non-critical or experimental workloads where budget is a priority.
- STANDARD3-X (General Purpose Instances)
  - Use Case: Designed for production-grade applications requiring a balanced mix of compute, memory, and network resources.
  - vCPU: Available with either shared or dedicated vCPUs (AMD EPYC™ 7003 series), offering flexibility in performance and cost.
  - Performance: More consistent than BASIC3-X, especially when using dedicated vCPUs.
  - Memory: Ranges from 2 GiB to 384 GiB.
  - Storage: Uses Resilient Block Storage only.
  - Bandwidth: Up to 12.8 Gbps.
  - Best For: Business-critical applications, high-traffic websites, SaaS platforms, and data analytics.
- COMPUTE3-X (Compute Optimized Instances)
  - Use Case: Tailored for compute-intensive workloads such as video encoding, machine learning inference, batch processing, and CI/CD pipelines.
  - vCPU: Dedicated vCPUs (AMD EPYC™ 7543), ensuring exclusive access to physical cores and consistent high performance.
  - Performance: Highest single-thread and multi-thread performance with no risk of CPU contention.
  - Memory: Ranges from 4 GiB to 512 GiB.
  - Storage: Resilient Block Storage only.
  - Bandwidth: Up to 12.8 Gbps.
  - Best For: Applications requiring sustained high CPU usage and low latency.

## Summary Comparison

| Feature | BASIC3-X| STANDARD3-X | COMPUTE3-X |
| --- | --- | --- | ---|
| Target | Workload	Development, testing, low-traffic sites | General production workloads | Compute-intensive tasks |
| vCPU Type | Shared | Shared or Dedicated | Dedicated |
| Performance | Consistency	Variable | High (especially with dedicated) | Very High |
| Memory Range | 2–128 GiB | 2–384 GiB | 4–512 GiB |
| Storage | Local or Block | Block only | Block only |
| Max Bandwidth | 10 Gbps |12.8 Gbps | 12.8 Gbps |

Choose BASIC3-X for cost-efficient development, STANDARD3-X for balanced production workloads, and COMPUTE3-X for high-performance computing tasks.

## All Flavors Comparison:

| Name | Range | vCPUs | vCPU Type | Memory | Storage | Bandwidth | Price (excl. tax) |
|---|---|---|---|---|---|---|---|
| BASIC3-X2C-4G | Basic | 2 | Shared | 4 GB | Block | 350 Mbps | €0.0383/hr |
| BASIC3-X2C-8G | Basic | 2 | Shared | 8 GB | Block | 350 Mbps | €0.0575/hr |
| BASIC3-X4C-8G | Basic | 4 | Shared | 8 GB | Block | 700 Mbps | €0.0767/hr |
| BASIC3-X4C-16G | Basic | 4 | Shared | 16 GB | Block | 700 Mbps | €0.115/hr |
| BASIC3-X8C-16G | Basic | 8 | Shared | 16 GB | Block | 1.5 Gbps | €0.1725/hr |
| BASIC3-X8C-32G | Basic | 8 | Shared | 32 GB | Block | 1.5 Gbps | €0.2299/hr |
| BASIC3-X16C-32G | Basic | 16 | Shared | 32 GB | Block | 3 Gbps | €0.3449/hr |
| BASIC3-X16C-64G | Basic | 16 | Shared | 64 GB | Block | 3 Gbps | €0.4598/hr |
| STANDARD3-X2C-8G | Standard | 2 | Dedicated | 8 GB | Block | 500 Mbps | €0.0809/hr |
| STANDARD3-X4C-16G | Standard | 4 | Dedicated | 16 GB | Block | 1 Gbps | €0.1617/hr |
| STANDARD3-X8C-32G | Standard | 8 | Dedicated | 32 GB | Block | 2 Gbps | €0.319/hr |
| STANDARD3-X16C-64G | Standard | 16 | Dedicated | 64 GB | Block | 4 Gbps | €0.649/hr |
| STANDARD3-X32C-128G | Standard | 32 | Dedicated | 128 GB | Block | 8 Gbps | €1.298/hr |
| STANDARD3-X48C-192G | Standard | 48 | Dedicated | 192 GB | Block | 16 Gbps | €1.947/hr |
| COMPUTE3-X2C-4G | Compute | 2 | Dedicated | 4 GB | Block | 500 Mbps | €0.0585/hr |
| COMPUTE3-X4C-8G | Compute | 4 | Dedicated | 8 GB | Block | 1 Gbps | €0.117/hr |
| COMPUTE3-X8C-16G | Compute | 8 | Dedicated | 16 GB | Block | 2 Gbps | €0.2341/hr |
| COMPUTE3-X16C-32G | Compute | 16 | Dedicated | 32 GB | Block | 4 Gbps | €0.4682/hr |
| COMPUTE3-X32C-64G | Compute | 32 | Dedicated | 64 GB | Block | 8 Gbps | €0.9363/hr |
| COMPUTE3-X48C-96G | Compute | 48 | Dedicated | 96 GB | Block | 16 Gbps | €1.397/hr |
| COMPUTE3-X64C-128G | Compute | 64 | Dedicated | 128 GB | Block | 16 Gbps | €1.8726/hr |
| COMPUTE3-X96C-192G | Compute | 96 | Dedicated | 192 GB | Block | 16 Gbps | €2.794/hr |