Please implement an advanced Object-Oriented "Table One" Generator in Python using pandas and scipy.stats. 

I want the architecture to exactly mimic the 'shiny-stat' core concept. It must be divided into the following 5 distinct components:

1. Data Structures (`VariableAnalysis` dataclass)
   - Create a dataclass to hold the full analysis results for a single variable row.
   - Fields should include: `name`, `label`, `var_type`, `stats_overall`, `stats_groups` (dict), `p_value`, `test_name`, `or_test_name`, `extra_stats` (for SMD, OR).

2. Classifier Logic (`VariableClassifier` class)
   - Implement a static method for intelligent variable type inference.
   - Logic: 
     - Categorical: If not numeric, object/category dtype, or unique values <= 10.
     - Continuous: If numeric, test for normality. 
     - Normality check: Use Shapiro-Wilk (N < 5000) or Jarque-Bera (N >= 5000). Also consider descriptive criteria (absolute skewness < 1.0 and absolute kurtosis < 2.0 if N > 50).
   - Return one of: "categorical", "continuous_normal", "continuous_non_normal", "unknown".

3. Statistical Engine (`StatisticalEngine` class)
   - Encapsulate all statistical calculations as static methods.
   - Descriptive Stats: Mean ± SD (normal), Median [Q1, Q3] (non-normal), Count (Percentage%) (categorical).
   - P-values (Continuous): t-test (2 groups) / ANOVA (>2 groups) for normal. Mann-Whitney U (2 groups) / Kruskal-Wallis (>2 groups) for non-normal.
   - P-values (Categorical): Chi-square contingency, fallback to Fisher's Exact if 2x2 and min expected frequency < 5.
   - Extra Stats: Implement Standardized Mean Difference (SMD) and Odds Ratio (OR) calculations (Univariate Logistic for continuous, 2x2 with Haldane-Anscombe correction for categorical).

4. Formatter (`TableOneFormatter` class)
   - Handle the rendering of the `VariableAnalysis` results into the final output format (e.g., a pandas DataFrame or raw HTML).
   - Format p-values beautifully (e.g., "<0.001").

5. Main Generator (`TableOneGenerator` class)
   - The orchestrator class.
   - Initialize with the raw DataFrame and optional variable metadata (labels).
   - Have a `generate(selected_vars, stratify_by=None, or_style='all_levels')` method that orchestrates the Classifier, Statistical Engine, and Formatter to produce the final output.

Please write the complete Python code for this architecture. Ensure it is robust, modular, and handles missing data (NaNs) gracefully during calculations.
