# %%
import numpy as np
import xarray as xr

shape = (7, 5)

a1 = np.linspace(-2.1, -2.5, shape[0])
a2 = np.linspace(-2.3, -2.7, shape[0])
b = np.linspace(-4.2, -4.3, shape[1])


data1 = np.random.rand(*shape)
data2 = np.random.rand(*shape)

xr_ds = xr.Dataset(
    {"data1": (["a1", "b"], data1), "data2": (["a2", "b"], data2)},
    coords={
        "b": b,
        "a1": a1,
        "a2": a2,
    },
)
xr_ds

# %%
