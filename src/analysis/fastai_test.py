from fastai.tabular.all import *
import pandas as pd
import sys

from torch.nn.modules.activation import Softmax

pd.options.mode.chained_assignment = None

df = pd.read_csv(".csv", index_col=0)
df = df_shrink(df, int2uint=True)
splits = RandomSplitter(valid_pct=0.4)(range_of(df))

to = TabularPandas(df, procs=[Categorify, FillMissing, Normalize],
                   cat_names=['contributor_occupation', 'contributor_employer', 'contributor_city', 'contributor_state', 'contributor_zip'],
                   y_names='party',
                   splits=splits,
                   inplace=True)



dls = to.dataloaders(bs=1024)


f1score = F1Score(average="micro")
learn = tabular_learner(dls, layers=[300, 150], metrics=[accuracy, f1score])
learn.fit_one_cycle(5)
learn.show_results()
