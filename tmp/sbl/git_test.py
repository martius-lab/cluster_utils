from cluster.report import produce_basic_report
import pandas as pd
import numpy as np

dates = pd.date_range('20130101', periods=6)

relevant_params = ['B', 'C', 'D']
metrics = ['A']
submission_name = 'test_pdf'
output_pdf = '/tmp/test_pdf.pdf'

df = pd.DataFrame(np.random.randn(6,4), index=dates, columns=list('ABCD'))

produce_basic_report(df, relevant_params, metrics, procedure_name=submission_name,
                     output_file=output_pdf)
