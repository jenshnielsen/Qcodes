# %%
import numpy as np
import xarray as xr

# %%
shape = (7, 5)

vp1 = np.linspace(-2.1, -2.5, shape[0])
vp2 = np.linspace(-4.2, -4.3, shape[1])

vp11, vp22 = np.meshgrid(vp1, vp2, indexing="ij")
a = vp1 + 0.1
b = 1.01 * vp11 + 1.07 * vp22
c = 1e-3 * vp2

data = np.random.rand(*shape)

xr_ds = xr.Dataset(
    {"data": (["vp1", "vp2"], data)},
    coords={
        "vp1": vp1,
        "vp2": vp2,
        "a": ("vp1", a),
        "b": (["vp1", "vp2"], b),
        "c": ("vp2", c),
    },
)
xr_ds

# %%
