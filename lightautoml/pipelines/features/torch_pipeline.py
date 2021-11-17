from typing import Optional
from typing import Union

import numpy as np

from ...dataset.np_pd_dataset import NumpyDataset
from ...dataset.np_pd_dataset import PandasDataset
from ...dataset.roles import NumericRole
from ...transformers.base import ChangeRoles
from ...transformers.base import ColumnsSelector
from ...transformers.base import ConvertDataset
from ...transformers.base import LAMLTransformer
from ...transformers.base import SequentialTransformer
from ...transformers.base import UnionTransformer
from ...transformers.categorical import LabelEncoder
from ...transformers.datetime import TimeToNum
from ...transformers.numeric import FillInf
from ...transformers.numeric import FillnaMedian
from ...transformers.numeric import QuantileTransformer
from ...transformers.numeric import StandardScaler
from ..selection.base import ImportanceEstimator
from ..utils import get_columns_by_role
from .base import FeaturesPipeline
from .base import TabularDataFeatures


NumpyOrPandas = Union[PandasDataset, NumpyDataset]


class TorchSimpleFeatures(FeaturesPipeline):
    def __init__(self, use_qnt=True, output_qnt_dist="normal", **kwargs):
        super(TorchSimpleFeatures, self).__init__(**kwargs)
        self.use_qnt = use_qnt
        self.output_qnt_dist = output_qnt_dist

    def create_pipeline(self, train: NumpyOrPandas) -> LAMLTransformer:
        transformers_list = []

        # process categories
        categories = get_columns_by_role(train, "Category")
        if len(categories) > 0:
            cat_processing = SequentialTransformer(
                [ColumnsSelector(keys=categories), LabelEncoder()]
            )
            transformers_list.append(cat_processing)

        # process datetimes
        datetimes = get_columns_by_role(train, "Datetime")
        if len(datetimes) > 0:
            dt_processing = SequentialTransformer(
                [ColumnsSelector(keys=datetimes), TimeToNum()]
            )
            transformers_list.append(dt_processing)

        # process numbers
        numerics = get_columns_by_role(train, "Numeric")
        if len(numerics) > 0:
            num_processing = SequentialTransformer(
                [
                    ColumnsSelector(keys=numerics),
                    FillInf(),
                    FillnaMedian(),
                    QuantileTransformer(output_distribution=self.output_qnt_dist)
                    if self.use_qnt
                    else StandardScaler(),
                    ConvertDataset(dataset_type=NumpyDataset),
                    ChangeRoles(NumericRole(np.float32)),
                ]
            )
            transformers_list.append(num_processing)

        union_all = UnionTransformer(transformers_list)

        return union_all


class TorchSimpleFeatures_te_int(FeaturesPipeline, TabularDataFeatures):
    def __init__(
        self,
        feats_imp: Optional[ImportanceEstimator] = None,
        top_intersections: int = 5,
        max_bin_count: int = 10,
        max_intersection_depth: int = 3,
        subsample: Optional[Union[int, float]] = None,
        sparse_ohe: Union[str, bool] = "auto",
        auto_unique_co: int = 50,
        output_categories: bool = True,
        multiclass_te_co: int = 3,
        use_qnt=True,
        output_qnt_dist="normal",
        **kwargs
    ):

        assert (
            max_bin_count is None or max_bin_count > 1
        ), "Max bin count should be >= 2 or None"

        super().__init__(
            multiclass_te=False,
            top_intersections=top_intersections,
            max_intersection_depth=max_intersection_depth,
            subsample=subsample,
            feats_imp=feats_imp,
            auto_unique_co=auto_unique_co,
            output_categories=output_categories,
            ascending_by_cardinality=True,
            max_bin_count=max_bin_count,
            sparse_ohe=sparse_ohe,
            multiclass_te_co=multiclass_te_co,
        )
        self.use_qnt = use_qnt
        self.output_qnt_dist = output_qnt_dist

    def create_pipeline(self, train: NumpyOrPandas) -> LAMLTransformer:
        transformers_list = []

        target_encoder = self.get_target_encoder(train)

        # get target encoded categories
        te_part = self.get_categorical_raw(train, None)
        if te_part is not None and target_encoder is not None:
            transformers_list.append(SequentialTransformer([te_part, target_encoder()]))

        # get intersection of top categories
        intersections = self.get_categorical_intersections(train)
        if intersections is not None and target_encoder is not None:
            transformers_list.append(
                SequentialTransformer([intersections, target_encoder()])
            )

        # process datetimes
        datetimes = get_columns_by_role(train, "Datetime")
        if len(datetimes) > 0:
            dt_processing = SequentialTransformer(
                [ColumnsSelector(keys=datetimes), TimeToNum()]
            )
            transformers_list.append(dt_processing)

        numerics = get_columns_by_role(train, "Numeric")
        if len(numerics) > 0:
            num_processing = SequentialTransformer(
                [
                    ColumnsSelector(keys=numerics),
                    FillInf(),
                    FillnaMedian(),
                    QuantileTransformer(output_distribution=self.output_qnt_dist)
                    if self.use_qnt
                    else StandardScaler(),
                    ConvertDataset(dataset_type=NumpyDataset),
                    ChangeRoles(NumericRole(np.float32)),
                ]
            )
            transformers_list.append(num_processing)

        union_all = UnionTransformer(transformers_list)
        return union_all
