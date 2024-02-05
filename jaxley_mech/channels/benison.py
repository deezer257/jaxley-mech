from typing import Dict, Optional

import jax.numpy as jnp
from jaxley.channels import Channel
from jaxley.solver_gate import solve_gate_exponential, solve_inf_gate_exponential

from ..utils import efun

META = {
    "reference": "Benison, G., Keizer, J., Chalupa, L. M., & Robinson, D. W. (2001). Modeling Temporal Behavior of Postnatal Cat Retinal Ganglion Cells. Journal of Theoretical Biology, 210(2), 187–199. https://doi.org/10.1006/jtbi.2000.2289",
    "species": "Cat",
    "cell_type": "Retinal ganglion cells",
}


class Leak(Channel):
    """Leakage current"""

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        prefix = self._name
        self.channel_params = {
            f"{prefix}_gl": 0.25e-9,  # S/cm^2
            f"{prefix}_el": -60.0,  # mV
        }
        self.channel_states = {}
        self.META = META

    def update_states(
        self, u: Dict[str, jnp.ndarray], dt, voltages, params: Dict[str, jnp.ndarray]
    ):
        """No state to update."""
        return {}

    def compute_current(
        self, u: Dict[str, jnp.ndarray], voltages, params: Dict[str, jnp.ndarray]
    ):
        """Return current."""
        # Multiply with 1000 to convert Siemens to milli Siemens.
        prefix = self._name
        leak_conds = params[f"{prefix}_gl"] * 1000  # mS/cm^2
        return leak_conds * (voltages - params[f"{prefix}_el"])

    def init_state(self, voltages, params):
        """Initialize the state such at fixed point of gate dynamics."""
        return {}


class Na(Channel):
    """Sodium channel"""

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        prefix = self._name
        self.channel_params = {
            f"{prefix}_gNa": 150e-9,  # S/cm^2
            f"{prefix}_vNa": 75.0,  # mV
        }
        self.channel_states = {f"{prefix}_m": 0.2, f"{prefix}_h": 0.2}
        self.META = META

    def update_states(
        self,
        u: Dict[str, jnp.ndarray],
        dt: float,
        voltages: float,
        params: Dict[str, jnp.ndarray],
    ):
        "Update state."
        prefix = self._name
        ms, hs = u[f"{prefix}_m"], u[f"{prefix}_h"]
        m_new = solve_gate_exponential(ms, dt, *Na.m_gate(voltages))
        h_new = solve_gate_exponential(hs, dt, *Na.h_gate(voltages))
        return {f"{prefix}_m": m_new, f"{prefix}_h": h_new}

    def compute_current(
        self, u: Dict[str, jnp.ndarray], voltages, params: Dict[str, jnp.ndarray]
    ):
        "Return current."
        prefix = self._name
        ms, hs = u[f"{prefix}_m"], u[f"{prefix}_h"]
        na_conds = params[f"{prefix}_gNa"] * (ms**3) * hs * 1000  # mS/cm^2
        current = na_conds * (voltages - params[f"{prefix}_vNa"])
        return current

    def init_state(self, voltages, params):
        """Initialize the state such at fixed point of gate dynamics."""
        prefix = self._name
        alpha_m, beta_m = Na.m_gate(voltages)
        alpha_h, beta_h = Na.h_gate(voltages)
        return {
            f"{prefix}_m": alpha_m / (alpha_m + beta_m),
            f"{prefix}_h": alpha_h / (alpha_h + beta_h),
        }

    @staticmethod
    def m_gate(e):
        alpha = 0.5 * (e + 29) / (1 - jnp.exp(-0.18 * (e + 29)))
        beta = 6.0 * jnp.exp(-(e + 45.0) / 15.0)
        return alpha, beta

    @staticmethod
    def h_gate(e):
        alpha = 0.15 * jnp.exp(-(e + 47.0) / 20.0)
        beta = 2.8 / (1 + jnp.exp(-0.1 * (e + 20.0)))
        return alpha, beta


class Kdr(Channel):
    """Delayed Rectifier Potassium channel"""

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        prefix = self._name
        self.channel_params = {
            f"{prefix}_gKdr": 75e-9,  # S/cm^2
            "vK": -85.0,  # mV
        }
        self.channel_states = {f"{prefix}_m": 0.1}
        self.META = META

    def update_states(
        self, u: Dict[str, jnp.ndarray], dt, voltages, params: Dict[str, jnp.ndarray]
    ):
        """Update state."""
        prefix = self._name
        ms = u[f"{prefix}_m"]
        new_m = solve_gate_exponential(ms, dt, *Kdr.m_gate(voltages))
        return {f"{prefix}_m": new_m}

    def compute_current(
        self, u: Dict[str, jnp.ndarray], voltages, params: Dict[str, jnp.ndarray]
    ):
        """Return current."""
        prefix = self._name
        ms = u[f"{prefix}_m"]

        # Multiply with 1000 to convert Siemens to milli Siemens.
        kdr_conds = params[f"{prefix}_gKdr"] * (ms**3) * 1000  # mS/cm^2

        return kdr_conds * (voltages - params[f"vK"])

    def init_state(self, voltages, params):
        """Initialize the state such at fixed point of gate dynamics."""
        prefix = self._name
        alpha_m, beta_m = Kdr.m_gate(voltages)
        return {
            f"{prefix}_m": alpha_m / (alpha_m + beta_m),
        }

    @staticmethod
    def m_gate(e):
        alpha = 0.0065 * (e + 30) / (1 - jnp.exp(-0.3 * e))
        beta = 0.083 * jnp.exp((e + 15) / 15)
        return alpha, beta


class CaL(Channel):
    """L-type Calcium channel"""

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        prefix = self._name
        self.channel_params = {
            f"{prefix}_gCaL": 2e-9,  # S/cm^2
            "vCa": 45.0,  # mV
        }
        self.channel_states = {f"{prefix}_m": 0.1}
        self.META = META

    def update_states(
        self,
        u: Dict[str, jnp.ndarray],
        dt: float,
        voltages: float,
        params: Dict[str, jnp.ndarray],
    ):
        "Update state."
        prefix = self._name
        ms = u[f"{prefix}_m"]
        m_new = solve_gate_exponential(ms, dt, *CaL.m_gate(voltages))
        return {
            f"{prefix}_m": m_new,
        }

    def compute_current(
        self, u: Dict[str, jnp.ndarray], voltages, params: Dict[str, jnp.ndarray]
    ):
        "Return current."
        prefix = self._name
        ms = u[f"{prefix}_m"]
        CaL_conds = params[f"{prefix}_gCaL"] * (ms**2) * 1000  # mS/cm^2
        current = CaL_conds * (voltages - params[f"vCa"])
        return current

    def init_state(self, voltages, params):
        """Initialize the state such at fixed point of gate dynamics."""
        prefix = self._name
        alpha_m, beta_m = CaL.m_gate(voltages)
        return {
            f"{prefix}_m": alpha_m / (alpha_m + beta_m),
        }

    @staticmethod
    def m_gate(e):
        alpha = 0.061 * (e - 3.0) / (1 - jnp.exp(-(e - 3.0) / 12.5))
        beta = 0.058 * jnp.exp(-(e - 10.0) / 15.0)
        return alpha, beta


class CaN(Channel):
    """N-type Ca channel"""

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        prefix = self._name
        self.channel_params = {
            f"{prefix}_gCaN": 1.5e-9,  # S/cm^2
            "vCa": 45.0,  # mV
        }
        self.channel_states = {f"{prefix}_m": 0.2, f"{prefix}_h": 0.2}
        self.META = META

    def update_states(
        self,
        u: Dict[str, jnp.ndarray],
        dt: float,
        voltages: float,
        params: Dict[str, jnp.ndarray],
    ):
        "Update state."
        prefix = self._name
        ms, hs = u[f"{prefix}_m"], u[f"{prefix}_h"]
        m_new = solve_gate_exponential(ms, dt, *CaN.m_gate(voltages))
        h_new = solve_gate_exponential(hs, dt, *CaN.h_gate(voltages))
        return {f"{prefix}_m": m_new, f"{prefix}_h": h_new}

    def compute_current(
        self, u: Dict[str, jnp.ndarray], voltages, params: Dict[str, jnp.ndarray]
    ):
        "Return current."
        prefix = self._name
        ms, hs = u[f"{prefix}_m"], u[f"{prefix}_h"]
        CaN_conds = params[f"{prefix}_gCaN"] * (ms**2) * hs * 1000  # mS/cm^2
        current = CaN_conds * (voltages - params[f"vCa"])
        return current

    def init_state(self, voltages, params):
        """Initialize the state such at fixed point of gate dynamics."""
        prefix = self._name
        alpha_m, beta_m = CaN.m_gate(voltages)
        alpha_h, beta_h = CaN.h_gate(voltages)
        return {
            f"{prefix}_m": alpha_m / (alpha_m + beta_m),
            f"{prefix}_h": alpha_h / (alpha_h + beta_h),
        }

    @staticmethod
    def m_gate(e):
        alpha = 0.1 * (e - 20) / (1 - jnp.exp(-0.1 * (e - 20)))
        beta = 0.4 * jnp.exp(-(e + 25.0) / 18.0)
        return alpha, beta

    @staticmethod
    def h_gate(e):
        alpha = 0.01 * jnp.exp(-(e + 50.0) / 10.0)
        beta = 0.1 / (1 + jnp.exp(-(e + 17.0) / 17))
        return alpha, beta
