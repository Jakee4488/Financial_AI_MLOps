"""Feature Store manager for Unity Catalog integration.

Handles creating, updating, and retrieving feature tables
in Databricks Unity Catalog for training and serving.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class FeatureStoreManager:
    """Manage feature tables in Unity Catalog.

    Handles feature table creation, training set retrieval with
    point-in-time lookup, and online feature publishing.

    Usage:
        fsm = FeatureStoreManager(config, spark)
        fsm.create_feature_table(features_df)
        training_set = fsm.get_training_set()
    """

    def __init__(self, config: Any, spark: Any) -> None:
        """Initialize the Feature Store Manager.

        :param config: ProjectConfig with catalog/schema settings
        :param spark: SparkSession with Unity Catalog access
        """
        self.config = config
        self.spark = spark
        self.catalog = config.catalog_name
        self.schema = config.schema_name
        self.feature_table_name = f"{self.catalog}.{self.schema}.trade_features"
        self.train_table_name = f"{self.catalog}.{self.schema}.train_set"
        self.test_table_name = f"{self.catalog}.{self.schema}.test_set"

    def create_feature_table(self, features_df: Any, mode: str = "overwrite") -> None:
        """Create or update the feature table in Unity Catalog.

        :param features_df: Spark DataFrame with computed features
        :param mode: Write mode ('overwrite' or 'append')
        """
        from pyspark.sql.functions import current_timestamp, to_utc_timestamp

        logger.info(f"Writing features to {self.feature_table_name} (mode={mode})")

        features_with_ts = features_df.withColumn("update_timestamp_utc", to_utc_timestamp(current_timestamp(), "UTC"))

        features_with_ts.write.format("delta").mode(mode).saveAsTable(self.feature_table_name)

        # Enable CDF for monitoring
        self.spark.sql(f"ALTER TABLE {self.feature_table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true);")

        count = self.spark.table(self.feature_table_name).count()
        logger.info(f"Feature table {self.feature_table_name} now has {count} records")

    def save_training_sets(
        self,
        train_df: Any,
        test_df: Any,
    ) -> None:
        """Save training and test sets to Unity Catalog.

        :param train_df: Training set Spark DataFrame
        :param test_df: Test set Spark DataFrame
        """
        from pyspark.sql.functions import current_timestamp, to_utc_timestamp

        for df, table_name, label in [
            (train_df, self.train_table_name, "train"),
            (test_df, self.test_table_name, "test"),
        ]:
            df_with_ts = df.withColumn("update_timestamp_utc", to_utc_timestamp(current_timestamp(), "UTC"))
            df_with_ts.write.mode("overwrite").saveAsTable(table_name)

            self.spark.sql(f"ALTER TABLE {table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true);")
            logger.info(f"Saved {label} set to {table_name} ({df.count()} records)")

    def get_training_set(self) -> tuple[Any, Any]:
        """Retrieve training and test sets from Unity Catalog.

        :return: Tuple of (train_spark_df, test_spark_df)
        """
        train_df = self.spark.table(self.train_table_name)
        test_df = self.spark.table(self.test_table_name)
        logger.info(f"Loaded train ({train_df.count()}) and test ({test_df.count()}) sets")
        return train_df, test_df

    def get_feature_table_version(self) -> str:
        """Get the latest version of the feature table.

        :return: Latest Delta version as string
        """
        from delta.tables import DeltaTable

        dt = DeltaTable.forName(self.spark, self.feature_table_name)
        version = str(dt.history().select("version").first()[0])
        logger.info(f"Feature table version: {version}")
        return version

    def get_data_versions(self) -> dict[str, str]:
        """Get versions of train and test Delta tables.

        :return: Dictionary with train_version and test_version
        """
        from delta.tables import DeltaTable

        train_dt = DeltaTable.forName(self.spark, self.train_table_name)
        test_dt = DeltaTable.forName(self.spark, self.test_table_name)

        return {
            "train_version": str(train_dt.history().select("version").first()[0]),
            "test_version": str(test_dt.history().select("version").first()[0]),
        }
