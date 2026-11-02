"""Typed, planned statistical analyses of fixed tables. No provider calls."""
from __future__ import annotations

import math
import warnings

from ..analysis_core import fingerprint

VERSION = 'planned-statistics-1'
LEVELS = {'nominal', 'ordinal', 'interval', 'ratio'}
METHODS = {'auto', 'descriptive', 'welch', 'mann_whitney', 'paired_t', 'wilcoxon', 'one_sample',
    'welch_anova', 'kruskal', 'friedman', 'repeated_anova', 'chi_square', 'mcnemar',
    'pearson', 'spearman', 'kendall', 'linear', 'logistic', 'ordinal_logistic',
    'gee_binary', 'gee_count', 'mixed_linear', 'anova', 'ancova', 'reliability'}


def variable_catalog(fields, definitions):
    if not isinstance(definitions, list) or not definitions or len(definitions) > 30:
        raise ValueError('変数定義を1〜30件指定してください。')
    catalog = {}
    for raw in definitions:
        if not isinstance(raw, dict):
            raise ValueError('変数定義の形式が正しくありません。')
        field = raw.get('column')
        if field not in fields or field in catalog or raw.get('measurement_level') not in LEVELS:
            raise ValueError('列名の重複・未定義列・尺度を確認してください。')
        if raw.get('source') not in {'researcher', 'rule', 'ai'} or raw.get('validation_status') not in {'unvalidated', 'reviewed', 'validated'}:
            raise ValueError('変数の出所と検証状態を指定してください。')
        catalog[field] = {key: raw.get(key) for key in ('column', 'measurement_level', 'source',
            'validation_status', 'unit', 'definition_version', 'levels')}
    return catalog


def validate_plan(raw, catalog):
    if not isinstance(raw, dict) or raw.get('method', 'auto') not in METHODS:
        raise ValueError('統計計画の手法が正しくありません。')
    plan = {**raw, 'method': raw.get('method', 'auto'), 'mode': raw.get('mode', 'exploratory'),
        'min_n': raw.get('min_n', 5), 'alpha': raw.get('alpha', .05),
        'correction': raw.get('correction', 'holm'), 'analysis_unit': raw.get('analysis_unit', 'speaker')}
    if plan['mode'] not in {'exploratory', 'confirmatory'} or plan['analysis_unit'] not in {'speaker', 'participant', 'conversation', 'utterance', 'row'}:
        raise ValueError('探索・確認の区別と分析単位を指定してください。')
    if type(plan['min_n']) is not int or not 2 <= plan['min_n'] <= 100000:
        raise ValueError('最小Nは2〜100000の整数で指定してください。')
    if type(plan['alpha']) not in (int, float) or not 0 < plan['alpha'] < 1 or plan['correction'] not in {'holm', 'fdr_bh', 'none'}:
        raise ValueError('有意水準・多重比較補正を確認してください。')
    required = [plan.get('outcome')] + list(plan.get('predictors', []))
    required += [plan[key] for key in ('group', 'pair', 'cluster', 'unit_column') if plan.get(key)]
    if any(field not in catalog for field in required):
        raise ValueError('計画で使うすべての列に変数定義が必要です。')
    paired_methods = {'paired_t','wilcoxon','friedman','repeated_anova','mcnemar'}
    if plan['method'] in paired_methods and not (plan.get('pair') and plan.get('group')):
        raise ValueError('対応のある手法には対応IDと条件列が必要です。')
    if plan.get('pair') and plan['method'] not in paired_methods | {'auto','descriptive'}:
        raise ValueError('対応設計に独立標本の手法は指定できません。')
    if plan['method'] in {'welch','welch_anova','paired_t','repeated_anova','one_sample','linear','mixed_linear','anova','ancova'} and catalog[plan['outcome']]['measurement_level'] not in {'interval','ratio'}:
        raise ValueError('この手法には間隔・比率尺度の目的変数が必要です。')
    if plan['mode'] == 'confirmatory' and (plan.get('preregistered') is not True
            or any(catalog[field]['validation_status'] != 'validated' for field in required)):
        raise ValueError('確認的分析には事前登録と変数の妥当性検証が必要です。')
    if plan['analysis_unit'] == 'utterance' and plan['method'] not in {'descriptive', 'gee_binary', 'gee_count', 'mixed_linear'}:
        raise ValueError('発話を独立標本にはできません。話者単位へ集約するかクラスター対応手法を選んでください。')
    if plan['analysis_unit'] in {'speaker', 'participant', 'conversation'} and not plan.get('unit_column'):
        raise ValueError('分析単位を識別する列を指定してください。')
    return plan


def assemble(table, catalog, plan):
    import numpy as np
    selected = list(dict.fromkeys([plan['outcome'], *plan.get('predictors', []),
        *[plan[key] for key in ('group', 'pair', 'cluster', 'unit_column') if plan.get(key)]]))
    rows, omitted = [], []
    for index, row in enumerate(table['rows']):
        values = row['values']
        identity = row.get('row_id', str(index))
        if any(field not in values or values[field] is None or values[field] == '' for field in selected):
            omitted.append({'row_id': identity, 'reason': 'missing_value'})
            continue
        value = {field: values[field] for field in selected}
        for field in selected:
            definition = catalog[field]
            if definition['measurement_level'] in {'interval', 'ratio'}:
                if type(value[field]) not in (int, float) or not math.isfinite(value[field]):
                    raise ValueError(f'{field}に数値以外または非有限値があります。')
            elif not isinstance(value[field], (str, int, float, bool)) or isinstance(value[field], float) and not math.isfinite(value[field]):
                raise ValueError(f'{field}の分類値が正しくありません。')
        rows.append({**value, '_source_rows': [identity]})
    unit = plan.get('unit_column')
    # Repeated measures keep one observation per subject and condition.
    groups = {}
    if unit:
        for row in rows:
            key = (row[unit], row.get(plan.get('group'))) if plan.get('pair') else (row[unit],)
            groups.setdefault(key, []).append(row)
        aggregated = []
        for members in groups.values():
            combined = {'_source_rows': [identity for row in members for identity in row['_source_rows']]}
            for field in selected:
                definition = catalog[field]
                values = [row[field] for row in members]
                if definition['measurement_level'] in {'interval', 'ratio'} and field != unit:
                    combined[field] = float(np.mean(values))
                elif all(value == values[0] for value in values):
                    combined[field] = values[0]
                else:
                    raise ValueError(f'同一分析単位の{field}が一致しません。集約規則を確認してください。')
            aggregated.append(combined)
        rows = aggregated
    return rows, omitted


def run_statistics(table, definitions, raw_plan):
    import numpy as np
    from scipy import stats
    from statsmodels.stats.multitest import multipletests
    catalog = variable_catalog(table['fields'], definitions)
    plan = validate_plan(raw_plan, catalog)
    if len(table['rows']) > 100000:
        raise ValueError('統計の入力は100000行以内にしてください。')
    rows, omitted = assemble(table, catalog, plan)
    y_key, x_keys, group_key = plan['outcome'], plan.get('predictors', []), plan.get('group')
    y = np.array([r[y_key] for r in rows])
    group_labels = sorted({r[group_key] for r in rows}, key=str) if group_key else []
    def ordered_value(field, value):
        levels = catalog[field].get('levels')
        if type(value) in (int, float) and not (catalog[field]['measurement_level']=='ordinal' and levels is not None):
            return value
        if not isinstance(levels, list) or len(set(levels)) != len(levels) or value not in levels:
            raise ValueError('順序尺度には値と対応する順序付きlevelsが必要です。')
        return levels.index(value)
    groups = [np.array([ordered_value(y_key,r[y_key]) for r in rows if r[group_key] == label], dtype=float)
        for label in group_labels] if group_key and catalog[y_key]['measurement_level'] in {'ordinal', 'interval', 'ratio'} else []
    method = plan['method']
    if method == 'auto':
        if plan.get('pair') and group_key:
            if catalog[y_key]['measurement_level'] == 'nominal':
                if len(group_labels) != 2 or not set(y).issubset({0,1}):
                    raise ValueError('対応名義データの自動選択は二値・2条件のMcNemarに限ります。')
                method = 'mcnemar'
            elif catalog[y_key]['measurement_level'] == 'ordinal':
                method = 'wilcoxon' if len(group_labels) == 2 else 'friedman'
            else:
                method = 'paired_t' if len(group_labels) == 2 else 'repeated_anova'
        elif catalog[y_key]['measurement_level'] == 'nominal' and group_key:
            method = 'chi_square'
        elif catalog[y_key]['measurement_level'] == 'ordinal' and group_key:
            method = 'mann_whitney' if len(group_labels) == 2 else 'kruskal'
        elif groups:
            method = 'welch' if len(groups) == 2 else 'welch_anova'
        elif x_keys:
            method = 'spearman' if any(catalog[k]['measurement_level'] == 'ordinal' for k in [y_key, *x_keys]) else 'pearson'
        else:
            method = 'descriptive'
    result = {'method': method, 'status': 'not_computable', 'reason': '', 'n': len(rows), 'input_rows': len(table['rows']),
        'missing_rows': len(omitted), 'statistic': None, 'df': None, 'p': None, 'p_adjusted': None,
        'effect': None, 'ci_low': None, 'ci_high': None, 'groups': [], 'warnings': [], 'coefficients': []}
    if plan['mode'] == 'exploratory':
        result['warnings'].append('探索的分析です。変数の研究上の妥当性や母集団への一般化は保証しません。')
    if plan['analysis_unit'] == 'row':
        result['warnings'].append('行の独立性は研究者が確認する必要があります。')
    def numeric(field):
        if catalog[field]['measurement_level'] not in {'ordinal', 'interval', 'ratio'}:
            raise ValueError('数値・順序尺度の列を指定してください。')
        values = np.array([ordered_value(field,r[field]) for r in rows]) if catalog[field]['measurement_level']=='ordinal' else np.array([r[field] for r in rows])
        if not np.issubdtype(values.dtype, np.number):
            levels = catalog[field].get('levels')
            if not isinstance(levels, list) or len(set(levels)) != len(levels):
                raise ValueError('順序尺度には順序付きのlevelsが必要です。')
            values = np.array([levels.index(value) for value in values], dtype=float)
        return values.astype(float)
    def computed(test):
        result.update(status='completed', statistic=float(test.statistic), p=float(test.pvalue))
        if hasattr(test, 'df'):
            value = test.df
            result['df'] = [float(v) for v in value] if isinstance(value, tuple) else float(value)
    try:
        if len(rows) < plan['min_n']:
            raise ValueError('分析単位のNが計画の最小Nに届きません。')
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            if method == 'descriptive':
                values = numeric(y_key)
                result.update(status='completed', mean=float(np.mean(values)), median=float(np.median(values)),
                    sd=float(np.std(values, ddof=1)), minimum=float(np.min(values)), maximum=float(np.max(values)))
            elif method in {'welch', 'mann_whitney', 'welch_anova', 'kruskal'}:
                if len(groups) < 2 or any(len(group) < plan['min_n'] for group in groups):
                    raise ValueError('各群のNが最小Nに届かないか、群が2つ未満です。')
                result['groups'] = [{'group': label, 'n': len(values), 'mean': float(values.mean()), 'median': float(np.median(values))} for label, values in zip(group_labels, groups)]
                if method in {'welch', 'mann_whitney'} and len(groups) != 2:
                    raise ValueError('2群を指定してください。')
                if method == 'welch':
                    test = stats.ttest_ind(*groups, equal_var=False)
                    computed(test)
                    ci = test.confidence_interval(confidence_level=1-plan['alpha'])
                    result.update(ci_low=float(ci.low), ci_high=float(ci.high), ci_parameter='mean_difference')
                    a, b = groups
                    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
                    result['effect'] = float((a.mean()-b.mean())/pooled) if pooled else None
                    result['effect_type'] = 'cohen_d_pooled'
                elif method == 'mann_whitney':
                    computed(stats.mannwhitneyu(*groups, alternative='two-sided'))
                    result.update(effect=2*result['statistic']/(len(groups[0])*len(groups[1]))-1, effect_type='rank_biserial')
                elif method == 'kruskal':
                    computed(stats.kruskal(*groups))
                    result.update(effect=max(0., (result['statistic']-len(groups)+1)/(len(rows)-len(groups))), effect_type='epsilon_squared')
                else:
                    from statsmodels.stats.oneway import anova_oneway
                    test = anova_oneway(groups, use_var='unequal', welch_correction=True)
                    computed(test)
            elif method in {'paired_t', 'wilcoxon', 'friedman', 'repeated_anova', 'mcnemar'}:
                pair = plan.get('pair')
                if not pair or not group_key:
                    raise ValueError('対応IDと条件列を指定してください。')
                pairs = {}
                for row in rows:
                    values = pairs.setdefault(row[pair], {})
                    if row[group_key] in values:
                        raise ValueError('対応ID・条件の組が重複しています。')
                    values[row[group_key]] = row[y_key]
                complete = [p for p in pairs.values() if all(label in p for label in group_labels)]
                result['excluded_pairs'] = len(pairs)-len(complete)
                result['n'] = len(complete)
                if len(complete) < plan['min_n']:
                    raise ValueError('完全な対応ペアが最小Nに届きません。')
                matrix = np.array([[ordered_value(y_key,p[label]) for label in group_labels] for p in complete], dtype=float)
                if method in {'paired_t', 'wilcoxon', 'mcnemar'} and len(group_labels) != 2:
                    raise ValueError('対応する2条件を指定してください。')
                if method == 'paired_t':
                    computed(stats.ttest_rel(matrix[:,0],matrix[:,1]))
                    ci = stats.ttest_rel(matrix[:,0],matrix[:,1]).confidence_interval(confidence_level=1-plan['alpha'])
                    difference = matrix[:,0]-matrix[:,1]
                    result.update(ci_low=float(ci.low),ci_high=float(ci.high),ci_parameter='mean_difference',
                        effect=float(difference.mean()/difference.std(ddof=1)) if difference.std(ddof=1) else None,effect_type='cohen_dz')
                elif method == 'wilcoxon':
                    computed(stats.wilcoxon(matrix[:,0],matrix[:,1]))
                elif method == 'friedman':
                    if matrix.shape[1] < 3: raise ValueError('3条件以上を指定してください。')
                    computed(stats.friedmanchisquare(*matrix.T))
                elif method == 'mcnemar':
                    if not np.isin(matrix, [0,1]).all(): raise ValueError('McNemarは0/1の二値に限ります。')
                    b, c = int(np.sum((matrix[:,0]==0)&(matrix[:,1]==1))), int(np.sum((matrix[:,0]==1)&(matrix[:,1]==0)))
                    if b+c == 0: raise ValueError('不一致ペアがありません。')
                    test = stats.binomtest(b, b+c, p=.5)
                    result.update(status='completed',statistic=float(b),p=float(test.pvalue),discordant_pairs=b+c)
                else:
                    n,k = matrix.shape
                    if k < 3: raise ValueError('反復測定分散分析には3条件以上が必要です。')
                    error = matrix-matrix.mean(axis=1,keepdims=True)-matrix.mean(axis=0,keepdims=True)+matrix.mean()
                    sse = float(np.sum(error**2)); ssc = float(n*np.sum((matrix.mean(axis=0)-matrix.mean())**2))
                    if sse == 0: raise ValueError('誤差分散が0です。')
                    covariance = np.cov(matrix-matrix.mean(axis=1,keepdims=True), rowvar=False)
                    epsilon = min(1.,max(1/(k-1),float(np.trace(covariance)**2/((k-1)*np.trace(covariance@covariance)))))
                    statistic = (ssc/(k-1))/(sse/((n-1)*(k-1)))
                    result.update(status='completed',statistic=statistic,df=[epsilon*(k-1),epsilon*(n-1)*(k-1)],
                        p=float(stats.f.sf(statistic,epsilon*(k-1),epsilon*(n-1)*(k-1))),epsilon_gg=epsilon,
                        effect=ssc/(ssc+sse),effect_type='partial_eta_squared')
            elif method == 'one_sample':
                values = numeric(y_key)
                if type(plan.get('reference')) not in (int,float): raise ValueError('基準値を指定してください。')
                computed(stats.ttest_1samp(values,plan['reference']))
            elif method in {'pearson','spearman','kendall'}:
                if len(x_keys) != 1: raise ValueError('相関の説明変数は1列指定してください。')
                x,y = numeric(x_keys[0]),numeric(y_key)
                test = {'pearson':stats.pearsonr,'spearman':stats.spearmanr,'kendall':stats.kendalltau}[method](x,y)
                computed(test); result.update(effect=result['statistic'],effect_type=method)
                if method == 'pearson' and len(rows)>3:
                    ci=test.confidence_interval(confidence_level=1-plan['alpha'])
                    result.update(ci_low=float(ci.low),ci_high=float(ci.high),ci_parameter='correlation')
            elif method == 'chi_square':
                if not group_key: raise ValueError('分類の比較列を指定してください。')
                categories = sorted(set(y),key=str)
                observed=np.array([[sum(r[group_key]==g and r[y_key]==c for r in rows) for c in categories] for g in group_labels])
                if min(observed.shape)<2: raise ValueError('分類水準が不足しています。')
                test=stats.chi2_contingency(observed,correction=False)
                expected=test.expected_freq
                sparse=bool((expected<1).any() or np.mean(expected<5)>.2)
                result.update(expected_min=float(expected.min()),observed=observed.tolist(),expected=expected.tolist())
                if sparse and observed.shape==(2,2):
                    exact=stats.fisher_exact(observed)
                    result.update(status='completed',method='fisher_exact',statistic=float(exact.statistic) if math.isfinite(exact.statistic) else None,
                        p=float(exact.pvalue),odds_ratio_status='finite' if math.isfinite(exact.statistic) else 'infinite')
                elif sparse:
                    raise ValueError('期待度数が不足しています。R×Cの正確検定が必要です。')
                else:
                    result.update(status='completed',statistic=float(test.statistic),p=float(test.pvalue),df=int(test.dof))
                result.update(effect=float(np.sqrt(test.statistic/(observed.sum()*min(observed.shape[0]-1,observed.shape[1]-1)))),effect_type='cramers_v')
            elif method == 'reliability':
                matrix=np.column_stack([numeric(field) for field in [y_key,*x_keys]])
                k=matrix.shape[1]; variance=np.var(matrix.sum(axis=1),ddof=1)
                if k<2 or variance==0: raise ValueError('2項目以上と総得点の分散が必要です。')
                result.update(status='completed',effect=float(k/(k-1)*(1-np.var(matrix,axis=0,ddof=1).sum()/variance)),effect_type='cronbach_alpha')
            elif method in {'anova', 'ancova'}:
                import pandas as pd
                import statsmodels.formula.api as smf
                from statsmodels.stats.anova import anova_lm
                if not x_keys: raise ValueError('要因・共変量を指定してください。')
                frame = pd.DataFrame({'y': numeric(y_key), **{f'x{i}': [r[key] for r in rows] for i,key in enumerate(x_keys)}})
                terms = [f'C(x{i})' if catalog[key]['measurement_level'] in {'nominal','ordinal'} else f'x{i}' for i,key in enumerate(x_keys)]
                fitted = smf.ols('y ~ ' + ' + '.join(terms), data=frame).fit()
                if np.linalg.matrix_rank(fitted.model.exog) < fitted.model.exog.shape[1] or fitted.df_resid <= 0:
                    raise ValueError('設計行列が特異か、残差自由度が不足しています。')
                tests = anova_lm(fitted, typ=2)
                residual = float(tests.loc['Residual','sum_sq'])
                result.update(status='completed', terms=[{'term':str(term), 'statistic':float(row['F']),
                    'df':float(row['df']), 'p':float(row['PR(>F)']),
                    'partial_eta_squared':float(row['sum_sq']/(row['sum_sq']+residual))}
                    for term,row in tests.iterrows() if term!='Residual'])
            else:
                import pandas as pd
                import statsmodels.api as sm
                if not x_keys: raise ValueError('説明変数を指定してください。')
                column_budget = 1 + sum(len({r[field] for r in rows}) - 1 if catalog[field]['measurement_level'] in {'nominal','ordinal'} else 1 for field in x_keys)
                if column_budget > 100 or column_budget * len(rows) > 2_000_000:
                    raise ValueError('説明変数の水準数・推定行列が上限を超えています。変数や対象を絞ってください。')
                frame=pd.DataFrame([{f'x{i}':r[field] for i,field in enumerate(x_keys)} for r in rows])
                x=pd.get_dummies(frame,columns=[f'x{i}' for i,k in enumerate(x_keys) if catalog[k]['measurement_level'] in {'nominal','ordinal'}],drop_first=True,dtype=float).astype(float)
                y=numeric(y_key) if method not in {'logistic','gee_binary','ordinal_logistic'} else np.array([r[y_key] for r in rows])
                if method in {'logistic','gee_binary'} and not np.isin(y,[0,1]).all(): raise ValueError('二値モデルの目的変数は0/1にしてください。')
                if method=='ordinal_logistic':
                    from statsmodels.miscmodels.ordinal_model import OrderedModel
                    levels=catalog[y_key].get('levels')
                    if not isinstance(levels,list) or len(levels)<3: raise ValueError('順序目的変数のlevelsを3水準以上定義してください。')
                    y=np.array([levels.index(v) for v in y])
                    if np.linalg.matrix_rank(x.to_numpy()) < x.shape[1] or len(y) <= x.shape[1]:
                        raise ValueError('設計行列が特異か、残差自由度が不足しています。')
                    fit=OrderedModel(y,x,distr='logit').fit(method='bfgs',disp=False)
                    if not fit.mle_retvals.get('converged'): raise ValueError('順序モデルが収束しませんでした。')
                else:
                    x=sm.add_constant(x,has_constant='add')
                    if np.linalg.matrix_rank(x.to_numpy()) < x.shape[1] or len(y) <= x.shape[1]:
                        raise ValueError('設計行列が特異か、残差自由度が不足しています。')
                    cluster=plan.get('cluster')
                    if method in {'gee_binary','gee_count','mixed_linear'} and not cluster: raise ValueError('クラスターIDを指定してください。')
                    ids=np.array([r[cluster] for r in rows]) if cluster else None
                    if cluster and len(set(ids))<3: raise ValueError('クラスターが3件未満です。')
                    if method.startswith('gee_'):
                        if method=='gee_count' and (np.any(y<0) or np.any(y!=np.floor(y))): raise ValueError('計数モデルは非負整数に限ります。')
                        fit=sm.GEE(y,x,groups=ids,family=sm.families.Binomial() if method=='gee_binary' else sm.families.Poisson()).fit()
                    elif method=='mixed_linear':
                        fit=sm.MixedLM(y,x,groups=ids).fit(reml=False,disp=False)
                    elif method=='logistic':
                        fit=sm.Logit(y,x).fit(disp=False)
                        if not fit.mle_retvals.get('converged'): raise ValueError('二値モデルが収束しませんでした。')
                    else:
                        fit=sm.OLS(y,x).fit(cov_type='cluster',cov_kwds={'groups':ids}) if cluster else sm.OLS(y,x).fit(cov_type='HC3')
                    if getattr(fit,'converged',True) is not True: raise ValueError('モデルが収束しませんでした。')
                    if cluster and len(set(ids))<20: result['warnings'].append('クラスターが20件未満です。推定の不確実性に注意してください。')
                ci=np.asarray(fit.conf_int(alpha=plan['alpha']))
                names=list(getattr(fit.model,'exog_names',range(len(fit.params))))
                result.update(status='completed',n=int(fit.nobs),coefficients=[{'term':str(name),'estimate':float(value),
                    'p':float(p),'ci_low':float(bounds[0]),'ci_high':float(bounds[1])} for name,value,p,bounds in zip(names,fit.params,fit.pvalues,ci)])
            result['warnings'] += [str(w.message) for w in captured]
        numbers=[result[key] for key in ('statistic','p','effect','ci_low','ci_high') if result[key] is not None]
        numbers += [value for row in result['coefficients'] for key,value in row.items() if key!='term' and value is not None]
        if any(not math.isfinite(value) for value in numbers):
            raise ValueError('統計量・不確実性を有限値として算出できません。')
        tests_for_adjustment = result['coefficients'] or result.get('terms', [])
        pvalues = [row['p'] for row in tests_for_adjustment] if tests_for_adjustment else [result['p']] if result['p'] is not None else []
        if pvalues:
            corrected=multipletests(pvalues,method=plan['correction'])[1] if plan['correction']!='none' else pvalues
            if tests_for_adjustment:
                for coefficient,p in zip(tests_for_adjustment,corrected): coefficient['p_adjusted']=float(p)
            else: result['p_adjusted']=float(corrected[0])
    except (ValueError,TypeError,np.linalg.LinAlgError) as exc:
        result.update(status='not_computable',reason=str(exc),statistic=None,p=None,p_adjusted=None,effect=None,ci_low=None,ci_high=None,coefficients=[])
    result['report'] = (f"{result['method']}、分析単位N={result['n']}、p={result['p_adjusted']:.6g}（{plan['correction']}補正）。"
        if result['status']=='completed' and result['p_adjusted'] is not None else
        f"{result['method']}、分析単位N={result['n']}。" if result['status']=='completed' else '算出不能：'+result['reason'])
    return {'schema_version':1,'method_version':VERSION,'plan':plan,'plan_hash':fingerprint(plan),
        'variable_catalog':list(catalog.values()),'catalog_hash':fingerprint(catalog),
        'analysis_rows':rows,'omissions':omitted,'results':[result]}
