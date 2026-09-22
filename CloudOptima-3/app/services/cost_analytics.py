from app.services.csv_store import InMemoryCSVStore

class CostAnalytics:
    def __init__(self):
        self.store = InMemoryCSVStore()

    def get_max_to_min_cost(self, limit: int = 15):
        df = self.store.master_df
        if df.empty:
            return []
        grouped = df.groupby('service')['cost'].sum().reset_index()
        grouped = grouped[grouped['cost'] > 0].sort_values(by='cost', ascending=False).head(limit)
        grouped['cost'] = grouped['cost'].round(2)
        grouped.rename(columns={'cost': 'total_cost'}, inplace=True)
        return grouped.to_dict(orient='records')

    def get_most_to_least_used(self, limit: int = 15):
        df = self.store.master_df
        if df.empty:
            return []
        
        grouped = df.groupby('service')['usage_quantity'].sum().reset_index()
        grouped = grouped[grouped['usage_quantity'] > 0].sort_values(by='usage_quantity', ascending=False).head(limit)
        grouped['usage_quantity'] = grouped['usage_quantity'].round(2)
        grouped.rename(columns={'usage_quantity': 'total_usage'}, inplace=True)
        return grouped.to_dict(orient='records')