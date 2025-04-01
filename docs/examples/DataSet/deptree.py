# %%
from qcodes.dataset import LinSweep, dond
from qcodes.parameters import DelegateParameter, Parameter

# %%

base = Parameter("base", set_cmd=None, get_cmd=None, initial_value=0)
source1 = Parameter("source1", set_cmd=None, get_cmd=None)
source2 = Parameter("source2", set_cmd=None, get_cmd=None)

del1 = DelegateParameter("del1", source=source1)
del2 = DelegateParameter("del2", source=source2)

# %%


sweep1 = LinSweep(del1, 0, 5, 10)
sweep2 = LinSweep(del2, 10, 15, 5)
# %%

dond(sweep1, sweep2, base)
# %%
