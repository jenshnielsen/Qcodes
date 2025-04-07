# %%

import numpy as np
import xarray as xr

x_var = [gate_state for gate_state in "XZZX"]
y_var = np.arange(len(x_var))

xr_ds = xr.Dataset({"y_var_name": ("x_var_name", y_var)}, coords={"x_var_name": x_var})
xr_ds
# %%

xr_ds["y_var_name"].plot()
