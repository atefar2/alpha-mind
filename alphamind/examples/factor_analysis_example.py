# -*- coding: utf-8 -*-
"""
Created on 2017-8-16

@author: cheng.li
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from alphamind.api import *
from PyFin.api import *


strategies = {
    'prod': {
        # 'factors': ['RVOL', 'EPS', 'DROEAfterNonRecurring', 'DivP', 'CFinc1', 'BDTO'],
        # 'weights': [0.05, 0.3, 0.35, 0.075, 0.15, 0.05]
        'factors': ['CHV'],
        'weights': [1.]
    },
    # 'candidate': {
    #     'factors': ['RVOL', 'EPS', 'CFinc1', 'BDTO', 'VAL', 'GREV', 'ROEDiluted'],
    #     'weights': [0.02, 0.2, 0.15, 0.05, 0.2, 0.2, 0.2]
    # }
}


engine = SqlEngine("mssql+pymssql://licheng:A12345678!@10.63.6.220/alpha")
universe = Universe('custom', ['zz500'])
benchmark_code = 905
neutralize_risk = industry_styles
constraint_risk = industry_styles
freq = '1w'

if freq == '1m':
    horizon = 21
elif freq == '1w':
    horizon = 4
elif freq == '1d':
    horizon = 0

dates = makeSchedule('2017-01-01',
                     '2017-08-20',
                     tenor=freq,
                     calendar='china.sse')

total_data_dict = {}

for strategy in strategies:
    factors = strategies[strategy]['factors']
    factor_weights = strategies[strategy]['weights']

    all_data = engine.fetch_data_range(universe, factors, dates=dates, benchmark=905)
    factor_all_data = all_data['factor']
    factor_groups = factor_all_data.groupby('Date')

    rets = []
    for i, value in enumerate(factor_groups):
        date = value[0]
        data = value[1]
        codes = data.Code.tolist()
        ref_date = date.strftime('%Y-%m-%d')
        returns = engine.fetch_dx_return(ref_date, codes, horizon=horizon)

        total_data = pd.merge(data, returns, on=['Code']).dropna()
        print(date, ': ', len(total_data))
        risk_exp = total_data[neutralize_risk].values.astype(float)
        industry = total_data.industry_code.values
        dx_return = total_data.dx.values
        benchmark = total_data.weight.values

        constraint_exp = total_data[constraint_risk].values
        risk_exp_expand = np.concatenate((constraint_exp, np.ones((len(risk_exp), 1))), axis=1).astype(float)

        risk_names = constraint_risk + ['total']
        risk_target = risk_exp_expand.T @ benchmark

        lbound = np.zeros(len(total_data))
        ubound = 0.01 + benchmark

        constraint = Constraints(risk_exp_expand, risk_names)
        for i, name in enumerate(risk_names):
            constraint.set_constraints(name, lower_bound=risk_target[i], upper_bound=risk_target[i])

        f_data = total_data[factors]
        try:
            pos, analysis = factor_analysis(f_data,
                                            factor_weights,
                                            industry=industry,
                                            d1returns=dx_return,
                                            risk_exp=risk_exp,
                                            benchmark=benchmark,
                                            is_tradable=total_data.isOpen.values.astype(bool),
                                            method='risk_neutral',
                                            constraints=constraint,
                                            use_rank=50,
                                            lbound=lbound,
                                            ubound=ubound)
        except Exception as e:
            print(e)
            rets.append(0.)
        else:
            rets.append(analysis.er[-1] / benchmark.sum())

    total_data_dict[strategy] = rets


ret_df = pd.DataFrame(total_data_dict, index=dates)

start_date = advanceDateByCalendar('china.sse', dates[0], '-1w')
ret_df.loc[start_date] = 0.
ret_df.sort_index(inplace=True)

ret_df.cumsum().plot(figsize=(12, 6))
plt.savefig("backtest_big_universe_20170814.png")
plt.show()