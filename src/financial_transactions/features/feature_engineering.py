"""Feature engineering for financial trade anomaly detection.

Computes windowed aggregations, technical indicators, and anomaly labels
from Silver/Gold trade data for model training.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


class FeatureEngineer:
    """Compute features for financial market anomaly detection.

    Supports both batch (pandas) and streaming (PySpark) computation modes.

    Usage:
        fe = FeatureEngineer(config, spark)
        features_df = fe.compute_all_features(silver_df)
        labeled_df = fe.generate_anomaly_labels(features_df)
    """

    def __init__(self, config: Any, spark: Any | None = None) -> None:
        """Initialize the feature engineer.

        :param config: ProjectConfig with feature definitions
        :param spark: SparkSession for PySpark operations
        """
        self.config = config
        self.spark = spark
        self.num_features = config.num_features
        self.cat_features = config.cat_features
        self.target = config.target

    def compute_trade_features_pandas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trade features using pandas (batch mode).

        :param df: DataFrame with Silver-level trade data
        :return: DataFrame with computed features
        """
        logger.info(f"Computing trade features for {len(df)} records...")
        df = df.copy()

        # Sort by symbol and timestamp
        df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

        # Group by symbol for windowed features
        for symbol in df["symbol"].unique():
            mask = df["symbol"] == symbol
            symbol_data = df.loc[mask].copy()

            # Price change percentage
            symbol_data["price_change_pct"] = symbol_data["price"].pct_change() * 100

            # Rolling statistics (14-period window)
            symbol_data["rolling_avg_price"] = symbol_data["price"].rolling(14, min_periods=1).mean()
            symbol_data["rolling_std_price"] = symbol_data["price"].rolling(14, min_periods=1).std()
            symbol_data["rolling_avg_volume"] = symbol_data["volume"].rolling(14, min_periods=1).mean()
            symbol_data["rolling_std_volume"] = symbol_data["volume"].rolling(14, min_periods=1).std()

            # Volume z-score
            symbol_data["volume_zscore"] = np.where(
                symbol_data["rolling_std_volume"] > 0,
                (symbol_data["volume"] - symbol_data["rolling_avg_volume"]) / symbol_data["rolling_std_volume"],
                0.0,
            )

            # Price volatility (1h proxy using rolling std)
            symbol_data["price_volatility_1h"] = symbol_data["rolling_std_price"].fillna(0)

            # Trade intensity (count in rolling window)
            symbol_data["trade_intensity_1m"] = symbol_data["price"].rolling(14, min_periods=1).count()

            # VWAP deviation
            rolling_vwap_num = (symbol_data["price"] * symbol_data["volume"]).rolling(14, min_periods=1).sum()
            rolling_vwap_den = symbol_data["volume"].rolling(14, min_periods=1).sum()
            symbol_data["vwap"] = np.where(rolling_vwap_den > 0, rolling_vwap_num / rolling_vwap_den, symbol_data["price"])
            symbol_data["vwap_deviation"] = np.where(
                symbol_data["vwap"] > 0,
                ((symbol_data["price"] - symbol_data["vwap"]) / symbol_data["vwap"]) * 100,
                0.0,
            )

            # RSI (14-period)
            delta = symbol_data["price"].diff()
            gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=1).mean()
            rs = np.where(loss > 0, gain / loss, 0)
            symbol_data["rsi_14"] = 100 - (100 / (1 + rs))

            # MACD (12 EMA - 26 EMA)
            ema_12 = symbol_data["price"].ewm(span=12, adjust=False).mean()
            ema_26 = symbol_data["price"].ewm(span=26, adjust=False).mean()
            symbol_data["macd_signal"] = ema_12 - ema_26

            # Bollinger Band position
            upper = symbol_data["rolling_avg_price"] + 2 * symbol_data["rolling_std_price"]
            lower = symbol_data["rolling_avg_price"] - 2 * symbol_data["rolling_std_price"]
            band_width = upper - lower
            symbol_data["bollinger_position"] = np.where(
                band_width > 0,
                (symbol_data["price"] - lower) / band_width,
                0.5,
            )

            # Bid-ask spread proxy
            symbol_data["bid_ask_spread_pct"] = np.where(
                symbol_data["price"] > 0,
                (symbol_data["rolling_std_price"] / symbol_data["price"]) * 100,
                0.0,
            )

            df.loc[mask] = symbol_data

        # Fill NaN from rolling window edges
        feature_cols = [
            "price_change_pct", "volume_zscore", "price_volatility_1h",
            "trade_intensity_1m", "vwap_deviation", "rsi_14",
            "macd_signal", "bollinger_position", "bid_ask_spread_pct",
        ]
        df[feature_cols] = df[feature_cols].fillna(0)

        # Time features (ensure they exist)
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"])
            df["hour_of_day"] = ts.dt.hour
            df["minute_of_hour"] = ts.dt.minute

        logger.info(f"Feature computation complete. Shape: {df.shape}")
        return df

    def generate_anomaly_labels(
        self,
        df: pd.DataFrame,
        volume_threshold: float = 3.0,
        price_threshold: float = 2.0,
    ) -> pd.DataFrame:
        """Generate anomaly labels using statistical thresholds.

        An observation is labeled as anomalous if:
        - volume_zscore > volume_threshold AND price_change_pct > price_threshold
        - OR rsi_14 > 85 or rsi_14 < 15 (extreme overbought/oversold)
        - OR bollinger_position > 1.0 or bollinger_position < 0.0 (outside Bollinger Bands)

        :param df: DataFrame with computed features
        :param volume_threshold: Z-score threshold for volume anomaly
        :param price_threshold: Absolute price change % threshold
        :return: DataFrame with is_anomaly column added
        """
        df = df.copy()

        # Combined anomaly criteria
        volume_anomaly = df["volume_zscore"].abs() > volume_threshold
        price_anomaly = df["price_change_pct"].abs() > price_threshold
        rsi_extreme = (df["rsi_14"] > 85) | (df["rsi_14"] < 15)
        bollinger_break = (df["bollinger_position"] > 1.0) | (df["bollinger_position"] < 0.0)

        df[self.target] = (
            (volume_anomaly & price_anomaly) | rsi_extreme | bollinger_break
        ).astype(int)

        anomaly_rate = df[self.target].mean() * 100
        logger.info(f"Generated anomaly labels: {anomaly_rate:.2f}% anomaly rate ({df[self.target].sum()}/{len(df)})")

        return df

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare training and test sets from feature data.

        :param df: DataFrame with features and labels
        :param test_size: Proportion for test split
        :param random_state: Random seed
        :return: Tuple of (train_df, test_df)
        """
        from sklearn.model_selection import train_test_split

        # Ensure all feature columns exist
        all_features = self.num_features + self.cat_features + [self.target]
        available = [c for c in all_features if c in df.columns]
        df_subset = df[available].dropna(subset=[self.target])

        train_set, test_set = train_test_split(
            df_subset, test_size=test_size, random_state=random_state,
            stratify=df_subset[self.target],
        )

        logger.info(f"Train: {len(train_set)}, Test: {len(test_set)}")
        logger.info(f"Train anomaly rate: {train_set[self.target].mean():.3f}")
        logger.info(f"Test anomaly rate: {test_set[self.target].mean():.3f}")

        return train_set, test_set
