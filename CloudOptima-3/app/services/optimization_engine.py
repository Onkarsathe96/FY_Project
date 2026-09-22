import pandas as pd

from app.services.csv_store import InMemoryCSVStore


class OptimizationEngine:
    def __init__(self):
        self.store = InMemoryCSVStore()

    def _service_profile(self, service_name, service_df):
        if service_df.empty:
            return {
                "kind": "generic",
                "cost_spike_ratio": 0.0,
                "low_usage_ratio": 0.0,
                "storage_like_ratio": 0.0,
                "compute_like_ratio": 0.0,
                "network_like_ratio": 0.0,
                "top_usage_type": "general",
            }

        cost_values = pd.to_numeric(service_df.get('cost', pd.Series([0.0] * len(service_df))), errors='coerce').fillna(0.0)
        usage_values = pd.to_numeric(service_df.get('usage_quantity', pd.Series([1.0] * len(service_df))), errors='coerce').fillna(1.0)

        total_cost = float(cost_values.sum())
        avg_cost = float(cost_values.mean()) if len(cost_values) else 0.0
        median_cost = float(cost_values.median()) if len(cost_values) else 0.0
        high_cost_ratio = float((cost_values > max(avg_cost, median_cost)).mean()) if len(cost_values) else 0.0

        usage_mean = float(usage_values.mean()) if len(usage_values) else 0.0
        usage_std = float(usage_values.std(ddof=0)) if len(usage_values) else 0.0
        usage_coefficient = 0.0 if usage_mean == 0 else usage_std / usage_mean
        low_usage_ratio = float((usage_values <= max(usage_mean * 0.5, 1.0)).mean()) if len(usage_values) else 0.0

        usage_types = service_df.get('usage_type', pd.Series([''] * len(service_df))).fillna('').astype(str).str.lower()
        storage_like_ratio = float(usage_types.str.contains('storage|archive|cold|retention|log|snapshot|backup', regex=True).mean())
        compute_like_ratio = float(usage_types.str.contains('compute|instance|vm|cpu|db|database|memory|lambda', regex=True).mean())
        network_like_ratio = float(usage_types.str.contains('nat|elb|gateway|network|traffic|loadbalancer|vpc', regex=True).mean())

        counts = usage_types.value_counts()
        top_usage_type = str(counts.idxmax()) if not counts.empty else 'general'

        return {
            "kind": service_name,
            "cost_spike_ratio": high_cost_ratio,
            "low_usage_ratio": low_usage_ratio,
            "storage_like_ratio": storage_like_ratio,
            "compute_like_ratio": compute_like_ratio,
            "network_like_ratio": network_like_ratio,
            "top_usage_type": top_usage_type,
            "total_cost": total_cost,
        }

    def calculate_savings_ratio(self, service_name, service_df):
        """Estimate the feasible savings ratio from the actual dataset for this service."""
        profile = self._service_profile(service_name, service_df)
        total_cost = profile["total_cost"]
        if total_cost <= 0:
            return 0.0

        ratio = (
            profile["cost_spike_ratio"] * 0.18 +
            max(profile["storage_like_ratio"], profile["compute_like_ratio"], profile["network_like_ratio"]) * 0.12 +
            min((profile["low_usage_ratio"] * 0.15) + (profile["cost_spike_ratio"] * 0.10), 0.25)
        )

        return round(min(max(ratio, 0.05), 0.45), 4)

    def calculate_potential_savings(self, service_name, service_df):
        if service_df.empty:
            return 0.0

        total_cost = float(pd.to_numeric(service_df['cost'], errors='coerce').fillna(0.0).sum())
        return round(total_cost * self.calculate_savings_ratio(service_name, service_df), 2)

    def _data_driven_description(self, service_name, service_df, profile):
        total_cost = float(profile["total_cost"])
        low_usage_ratio = profile["low_usage_ratio"]
        cost_spike_ratio = profile["cost_spike_ratio"]
        top_usage_type = profile["top_usage_type"]

        usage_costs = service_df.groupby('usage_type', dropna=False)['cost'].sum().sort_values(ascending=False)
        top_usage_cost = float(usage_costs.iloc[0]) if not usage_costs.empty else 0.0
        top_usage_share = (top_usage_cost / total_cost) if total_cost > 0 else 0.0

        usage_values = pd.to_numeric(service_df.get('usage_quantity', pd.Series([1.0] * len(service_df))), errors='coerce').fillna(1.0)
        usage_threshold = float(usage_values.quantile(0.25)) if len(usage_values) else 0.0
        low_usage_rows = int((usage_values <= max(usage_threshold, 1.0)).sum()) if len(usage_values) else 0

        if profile["storage_like_ratio"] >= profile["compute_like_ratio"] and profile["storage_like_ratio"] >= profile["network_like_ratio"]:
            return (
                f"{service_name} totals ${total_cost:.2f} across {len(service_df)} uploaded rows. "
                f"The largest cost contributor is {top_usage_type} at ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total). "
                f"{low_usage_rows} rows are at or below {usage_threshold:.2f} usage units, so review the low-usage storage entries before changing retention or tiering rules."
            )
        if profile["compute_like_ratio"] >= profile["storage_like_ratio"] and profile["compute_like_ratio"] >= profile["network_like_ratio"]:
            return (
                f"{service_name} totals ${total_cost:.2f} across {len(service_df)} rows. "
                f"{top_usage_type} contributes ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of spend), and {low_usage_ratio * 100:.0f}% of rows are below the median usage level. "
                f"Review the low-usage compute entries and the highest-cost usage buckets before resizing or consolidating workloads."
            )
        if profile["network_like_ratio"] >= profile["storage_like_ratio"] and profile["network_like_ratio"] >= profile["compute_like_ratio"]:
            return (
                f"{service_name} totals ${total_cost:.2f} across {len(service_df)} rows. "
                f"The biggest network-related spend is in {top_usage_type} at ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total), and {low_usage_rows} rows sit at low usage levels. "
                f"Check those low-volume traffic or endpoint entries before removing or consolidating any network resources."
            )
        return (
            f"{service_name} totals ${total_cost:.2f} across {len(service_df)} rows. "
            f"The highest-cost usage bucket is {top_usage_type} at ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of spend), while {low_usage_ratio * 100:.0f}% of rows are low-usage and {cost_spike_ratio * 100:.0f}% are unusually expensive. "
            f"Review the largest cost drivers and the low-usage entries before making budget or tagging changes."
        )

    def _recommendation_details(self, service_name, service_df, profile):
        total_cost = float(profile["total_cost"])
        usage_types = service_df.get('usage_type', pd.Series([''] * len(service_df))).fillna('').astype(str)
        usage_costs = service_df.groupby('usage_type', dropna=False)['cost'].sum().sort_values(ascending=False)
        top_usage_type = usage_costs.index[0] if not usage_costs.empty else profile["top_usage_type"]
        top_usage_cost = float(usage_costs.iloc[0]) if not usage_costs.empty else 0.0
        top_usage_share = (top_usage_cost / total_cost) if total_cost > 0 else 0.0

        usage_values = pd.to_numeric(service_df.get('usage_quantity', pd.Series([1.0] * len(service_df))), errors='coerce').fillna(1.0)
        usage_threshold = float(usage_values.quantile(0.25)) if len(usage_values) else 0.0
        low_usage_rows = int((usage_values <= max(usage_threshold, 1.0)).sum()) if len(usage_values) else 0
        low_usage_percent = (low_usage_rows / len(service_df)) * 100 if len(service_df) else 0.0

        s_upper = str(service_name).upper()

        if "EC2" in s_upper or "COMPUTE" in s_upper:
            return {
                "type": "Compute Rightsizing & Capacity Review",
                "impact": "High",
                "action_required": (
                    f"Examine the {top_usage_type} cost bucket, which contributes ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total spend), "
                    f"and review whether any low-usage rows below {usage_threshold:.2f} units can be downsized or consolidated."
                ),
                "description": (
                    f"{service_name} is spending ${total_cost:.2f} across {len(service_df)} rows. "
                    f"The largest compute-related cost driver is {top_usage_type} with ${top_usage_cost:.2f} in spend, and {low_usage_percent:.0f}% of entries sit in low-usage ranges. "
                    f"Downsizing or consolidating the lower-usage workloads is the strongest optimization opportunity in this dataset."
                )
            }
        if "S3" in s_upper or "GLACIER" in s_upper or "STORAGE" in s_upper:
            return {
                "type": "Storage Lifecycle & Tier Optimization",
                "impact": "Medium",
                "action_required": (
                    f"Use the CSV to isolate the {top_usage_type} entries, which represent ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of spend), and move the oldest or least-used rows into lower-cost archival tiers."
                ),
                "description": (
                    f"{service_name} totals ${total_cost:.2f} across {len(service_df)} rows. "
                    f"{top_usage_type} contributes the largest share of spend at ${top_usage_cost:.2f}, and {low_usage_percent:.0f}% of rows are low-usage or low-activity records. "
                    f"This points to a clear storage optimization path: reclassify older data and reduce spend on seldom-used tiers."
                )
            }
        if "RDS" in s_upper or "AURORA" in s_upper or "DATABASE" in s_upper or "DB" in s_upper:
            return {
                "type": "Database Capacity & Scheduling Review",
                "impact": "High",
                "action_required": (
                    f"Check the {top_usage_type} database cost bucket, which is ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of spend), and identify any non-production workloads below the usage threshold that can be scheduled or resized."
                ),
                "description": (
                    f"{service_name} totals ${total_cost:.2f}. The dataset shows {top_usage_type} as the dominant database spend segment with ${top_usage_cost:.2f}, and {low_usage_percent:.0f}% of rows are below the low-usage threshold. "
                    f"This suggests a strong case for right-sizing, scheduled shutdowns, or reducing redundant database capacity in lower-priority workloads."
                )
            }
        if "LAMBDA" in s_upper or "SERVERLESS" in s_upper:
            return {
                "type": "Serverless Efficiency Tuning",
                "impact": "Medium",
                "action_required": (
                    f"Review the {top_usage_type} function cost pattern, which is ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total), and reduce over-provisioned memory or runtime settings on the lowest-usage executions."
                ),
                "description": (
                    f"{service_name} is showing ${total_cost:.2f} in the uploaded data, with {top_usage_type} accounting for ${top_usage_cost:.2f} of that spend. "
                    f"Because {low_usage_percent:.0f}% of rows fall in the low-usage range, memory tuning and shorter execution windows are likely to improve efficiency without changing workload behavior."
                )
            }
        if "ELB" in s_upper or "LOAD" in s_upper or "VPC" in s_upper or "NAT" in s_upper or "GATEWAY" in s_upper:
            return {
                "type": "Network Cleanup & Traffic Review",
                "impact": "Medium",
                "action_required": (
                    f"Inspect the {top_usage_type} traffic entries, which contribute ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of cost), and remove unused or low-volume network endpoints before restructuring routing."
                ),
                "description": (
                    f"{service_name} totals ${total_cost:.2f} across {len(service_df)} rows. "
                    f"The network-heavy spend is concentrated in {top_usage_type}, and {low_usage_percent:.0f}% of entries remain in the low-usage band. "
                    f"This suggests idle or underused traffic paths can be cleaned up or merged to lower supporting network cost."
                )
            }
        if "LOG" in s_upper or "CLOUDWATCH" in s_upper:
            return {
                "type": "Log Retention & Storage Reduction",
                "impact": "Low",
                "action_required": (
                    f"Reduce retention for the {top_usage_type} log records, which account for ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total), and lower retention on low-value log sets that are not tied to active troubleshooting."
                ),
                "description": (
                    f"{service_name} currently totals ${total_cost:.2f}. The highest log-related spend is in {top_usage_type} at ${top_usage_cost:.2f}, and {low_usage_percent:.0f}% of rows are low-value entries. "
                    f"A targeted retention cut and log-pruning strategy will likely reduce spend without affecting critical monitoring."
                )
            }
        return {
            "type": "Spend Anomaly & Tag Governance",
            "impact": "Low",
            "action_required": (
                f"Review the {top_usage_type} cost bucket, which is ${top_usage_cost:.2f} ({top_usage_share * 100:.0f}% of total spend), and validate whether the low-usage rows are still needed or properly tagged."
            ),
            "description": (
                f"{service_name} totals ${total_cost:.2f} and the cost pattern is dominated by {top_usage_type}. "
                f"{low_usage_percent:.0f}% of rows fall in low-usage territory, so the strongest next step is to inspect ownership, tagging, and unused workloads tied to the highest-cost entries."
            )
        }

    def generate_recommendations(self):
        df = self.store.master_df
        actions = []
        if df.empty:
            return [{
                "service": "No Data Loaded",
                "type": "Manual Ingestion Required",
                "description": "Load one or more CSV files from the table on the left.",
                "potential_savings_monthly": 0.00,
                "impact": "Info",
                "action_required": "Click 'Load' on any CSV file."
            }]

        service_totals = df.groupby('service', dropna=False)['cost'].sum().to_dict()

        for service, total in service_totals.items():
            if total <= 0:
                continue

            service_df = df[df['service'] == service].copy()
            savings_ratio = self.calculate_savings_ratio(service, service_df)
            savings_amount = self.calculate_potential_savings(service, service_df)
            profile = self._service_profile(service, service_df)
            recommendation = self._recommendation_details(service, service_df, profile)

            actions.append({
                "service": service,
                "type": recommendation["type"],
                "description": recommendation["description"],
                "potential_savings_monthly": round(savings_amount, 2),
                "impact": recommendation["impact"],
                "action_required": recommendation["action_required"],
                "savings_ratio": savings_ratio,
            })

        return actions
