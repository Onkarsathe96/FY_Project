import glob
import os
import re

import pandas as pd

from app.config import DATA_DIR


class InMemoryCSVStore:
    """Singleton in-memory DataFrame store for manual CSV loading."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InMemoryCSVStore, cls).__new__(cls)
            cls._instance.master_df = pd.DataFrame(columns=[
                'date', 'service', 'usage_type', 'usage_quantity', 'cost', 'source_file'
            ])
            cls._instance.loaded_files = set()
        return cls._instance

    def list_files(self):
        """Lists all CSV files in data/ and their loaded status."""
        files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
        return [
            {
                "file_name": os.path.basename(f),
                "file_path": f,
                "size_mb": round(os.path.getsize(f) / (1024 * 1024), 2),
                "is_loaded": os.path.basename(f) in self.loaded_files
            }
            for f in sorted(files)
        ]

    def load_single_file(self, file_path: str):
        """Loads and parses a single CSV into the in-memory master DataFrame."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found.")

        filename = os.path.basename(file_path)
        if filename in self.loaded_files:
            return {"status": "already_loaded", "file": filename, "total_rows": len(self.master_df)}

        # Read CSV headers dynamically
        sample_df = pd.read_csv(file_path, nrows=50, low_memory=False)
        cols = {c.lower().replace(" ", "").replace("_", ""): c for c in sample_df.columns}

        possible_service_columns = [
            'serviceName', 'ServiceName', 'service', 'Service', 'Product Family', 'ProductFamily'
        ]
        inferred_service = next(
            (sample_df[col] for col in possible_service_columns if col in sample_df.columns),
            pd.Series([], dtype=object),
        )

        if isinstance(inferred_service, pd.Series) and not inferred_service.empty:
            non_null = inferred_service.dropna()
            if not non_null.empty:
                service_name = str(non_null.iloc[0]).strip()
            else:
                service_name = ''
        else:
            service_name = ''

        if not service_name:
            base_name = os.path.splitext(filename)[0]
            service_name = re.sub(r'(?i)^amazon', 'AWS', base_name)
            service_name = re.sub(r'(?i)aws', 'AWS', service_name)
            service_name = service_name.replace('_', ' ').replace('-', ' ').strip()

        if service_name.lower().startswith('amazon'):
            service_name = 'AWS ' + service_name[len('Amazon'):].strip()
        service_name = service_name.replace('AWS AWS ', 'AWS ')


        date_col = cols.get('date') or cols.get('effectivedate') or cols.get('usagestartdate')
        cost_col = cols.get('priceperunit') or cols.get('cost') or cols.get('unblendedcost') or cols.get('costusd')
        usage_col = cols.get('usagequantity') or cols.get('consumedquantity') or cols.get('unblendedrate')
        usage_type_col = cols.get('usagetype') or cols.get('operation') or cols.get('description')

        # Read file with Pandas
        df = pd.read_csv(file_path, low_memory=False, on_bad_lines='skip')
        cleaned = pd.DataFrame()

        # Standardize date
        if date_col and date_col in df.columns:
            cleaned['date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
        else:
            cleaned['date'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D').date
        cleaned['date'] = cleaned['date'].fillna(pd.Timestamp.now().date())

        cleaned['service'] = service_name

        # Standardize usage type
        if usage_type_col and usage_type_col in df.columns:
            cleaned['usage_type'] = df[usage_type_col].fillna("General").astype(str)
        else:
            cleaned['usage_type'] = "General"

        # Standardize usage quantity
        if usage_col and usage_col in df.columns:
            cleaned['usage_quantity'] = pd.to_numeric(
                df[usage_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce'
            ).fillna(1.0)
        else:
            cleaned['usage_quantity'] = 1.0

        # Standardize cost
        if cost_col and cost_col in df.columns:
            cleaned['cost'] = pd.to_numeric(
                df[cost_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce'
            ).fillna(0.0)
        else:
            cleaned['cost'] = cleaned['usage_quantity'] * 0.05

        cleaned['source_file'] = filename

        # Append to Master DataFrame
        self.master_df = pd.concat([self.master_df, cleaned], ignore_index=True)
        self.loaded_files.add(filename)

        return {
            "status": "success",
            "file": filename,
            "rows_added": len(cleaned),
            "total_records": len(self.master_df)
        }

    def clear(self):
        """Clears in-memory dataset."""
        self.master_df = pd.DataFrame(columns=[
            'date', 'service', 'usage_type', 'usage_quantity', 'cost', 'source_file'
        ])
        self.loaded_files.clear()
        return {"status": "Memory store cleared successfully"}