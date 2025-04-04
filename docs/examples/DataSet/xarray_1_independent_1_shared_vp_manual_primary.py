# %%
import numpy as np
import xarray as xr

shape = (7, 5)

vp1 = np.linspace(-2.1, -2.5, shape[0])
b = np.linspace(-4.2, -4.3, shape[1])

a1 = vp1 + 0.1
a2 = vp1 + 0.2

data1 = np.random.rand(*shape)
data2 = np.random.rand(*shape)

xr_ds = xr.Dataset(
    {"data1": (["a1", "b"], data1), "data2": (["a2", "b"], data2)},
    coords={
        "vp1": vp1,
        "b": b,
        "a1": ("vp1", a1),
        "a2": ("vp1", a2),
    },
)
xr_ds

# %%
