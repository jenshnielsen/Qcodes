import sys
from unittest.mock import MagicMock

import numpy as np
import pytest

# gclib requires proprietary Galil hardware drivers; mock it before importing
sys.modules["gclib"] = MagicMock()

from qcodes.instrument_drivers.Galil.dmc_41x3 import (  # noqa: E402
    GalilDMC4133Arm,
    _calculate_vector_component,
)

# --------------------------------------------------------------------------
# Tests for _calculate_vector_component
# --------------------------------------------------------------------------


class TestCalculateVectorComponent:
    def test_basic_calculation(self) -> None:
        """Known value: vec=1.0, val=2048 -> floor(1.0*2048)=2048, +1024=3072, rem=0 -> 3072"""
        result = _calculate_vector_component(vec=1.0, val=2048)
        assert result == 3072
        assert result % 1024 == 0

    def test_result_is_multiple_of_1024(self) -> None:
        """Result must always be a multiple of 1024 regardless of inputs."""
        test_cases = [
            (0.5, 2048),
            (0.3, 1500),
            (0.7, 3000),
            (1.0, 1024),
            (0.1, 500),
        ]
        for vec, val in test_cases:
            result = _calculate_vector_component(vec=vec, val=val)
            assert result % 1024 == 0, f"Failed for vec={vec}, val={val}: got {result}"

    def test_zero_vector_component(self) -> None:
        """vec=0 -> floor(0*val)=0, +1024=1024, rem=0 -> 1024."""
        result = _calculate_vector_component(vec=0.0, val=2048)
        assert result == 1024

    def test_negative_vector_component(self) -> None:
        """Negative vec uses abs(), so result should match positive vec."""
        result_pos = _calculate_vector_component(vec=0.5, val=2048)
        result_neg = _calculate_vector_component(vec=-0.5, val=2048)
        assert result_pos == result_neg

    def test_fractional_result_rounds_down_to_1024_boundary(self) -> None:
        """vec=0.3, val=1500 -> floor(0.3*1500)=450, +1024=1474, rem=1474%1024=450, 1474-450=1024."""
        result = _calculate_vector_component(vec=0.3, val=1500)
        assert result == 1024


# --------------------------------------------------------------------------
# Fixture for GalilDMC4133Arm._setup_motion tests
# --------------------------------------------------------------------------


@pytest.fixture
def mock_arm() -> MagicMock:
    arm = MagicMock(spec=GalilDMC4133Arm)
    arm.controller = MagicMock()
    arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}
    arm.controller.motor_a = MagicMock()
    arm.controller.motor_b = MagicMock()
    arm.controller.motor_c = MagicMock()
    # Plane equation: z >= 0 is above the chip plane
    arm._plane_eqn = np.array([0, 0, 1, 0])
    arm._acceleration = 2048
    arm._deceleration = 2048
    arm._target = None
    return arm


# --------------------------------------------------------------------------
# Tests for GalilDMC4133Arm._setup_motion
# --------------------------------------------------------------------------


class TestSetupMotion:
    def test_normal_motion_above_chip_plane(self, mock_arm: MagicMock) -> None:
        """Target is above chip plane (dot >= 0), motors get configured correctly."""
        rel_vec = np.array([1.0, 0.0, 0.0])
        d = 100.0
        speed = 500.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        # a=floor(1.0*100)=100, b=floor(0*100)=0, c=floor(0*100)=0
        # target = [100, 0, 0, 1], dot([0,0,1,0], [100,0,0,1]) = 0 >= 0 -> no correction
        mock_arm.controller.motor_a.relative_position.assert_called_once_with(100)
        mock_arm.controller.motor_b.relative_position.assert_called_once_with(0)
        mock_arm.controller.motor_c.relative_position.assert_called_once_with(0)

    def test_target_below_plane_correction_with_temp1_idx0(
        self, mock_arm: MagicMock
    ) -> None:
        """Target is below chip plane but correction found with temp1 on axis A (idx=0)."""
        # Plane: z >= 0. Position at origin.
        # Move in -z direction: target will be below plane.
        # rel_vec = [0.5, 0.0, -0.5], d = 2.0
        # a = floor(0.5*2) = 1, b = 0, c = floor(-0.5*2) = -1
        # target = [1, 0, -1, 1], dot([0,0,1,0], [1,0,-1,1]) = -1 < 0
        # idx=0: temp1=0, temp2=2
        #   target1 = [0, 0, -1, 1], dot = -1 < 0 -> no
        #   target2 = [2, 0, -1, 1], dot = -1 < 0 -> no
        # idx=1: temp1=-1, temp2=1
        #   target1 = [1, -1, -1, 1], dot = -1 < 0 -> no
        #   target2 = [1, 1, -1, 1], dot = -1 < 0 -> no
        # idx=2: temp1=-2, temp2=0
        #   target1 = [1, 0, -2, 1], dot = -2 < 0 -> no
        #   target2 = [1, 0, 0, 1], dot = 0 >= 0 -> yes! c = 0

        # Actually let me use a plane where temp1 on idx=0 works:
        # Use plane_eqn = [1, 0, 0, -5] meaning x >= 5 is "above"
        # pos = {"A": 10, "B": 0, "C": 0}
        # rel_vec = [-1, 0, 0], d = 6.0
        # a = floor(-1*6) = -6, b = 0, c = 0
        # target = [4, 0, 0, 1], dot([1,0,0,-5], [4,0,0,1]) = 4 - 5 = -1 < 0
        # idx=0: temp1 = -7, temp2 = -5
        #   target1 = [3, 0, 0, 1], dot = 3 - 5 = -2 < 0
        #   target2 = [5, 0, 0, 1], dot = 5 - 5 = 0 >= 0 -> a = temp2 = -5
        # This is temp2 on idx=0. Let me adjust for temp1:
        # Use plane_eqn = [-1, 0, 0, 5] meaning -x + 5 >= 0, i.e., x <= 5
        # pos = {"A": 0, "B": 0, "C": 0}
        # rel_vec = [1, 0, 0], d = 6.0
        # a = 6, b = 0, c = 0
        # target = [6, 0, 0, 1], dot([-1,0,0,5], [6,0,0,1]) = -6 + 5 = -1 < 0
        # idx=0: temp1 = 5, temp2 = 7
        #   target1 = [5, 0, 0, 1], dot = -5 + 5 = 0 >= 0 -> a = temp1 = 5 ✓

        mock_arm._plane_eqn = np.array([-1, 0, 0, 5])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}

        rel_vec = np.array([1.0, 0.0, 0.0])
        d = 6.0
        speed = 500.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        # After correction: a = 5 (temp1)
        mock_arm.controller.motor_a.relative_position.assert_called_once_with(5)

    def test_target_below_plane_correction_with_temp2(
        self, mock_arm: MagicMock
    ) -> None:
        """Target below chip plane, correction found with temp2 on axis A (idx=0)."""
        # plane_eqn = [1, 0, 0, -5]: dot >= 0 means x >= 5
        # pos = {"A": 10, "B": 0, "C": 0}
        # rel_vec = [-1, 0, 0], d = 6.0
        # a = -6, target = [4, 0, 0, 1], dot = 4-5 = -1 < 0
        # idx=0: temp1=-7, target1=[3,0,0,1], dot=3-5=-2 < 0
        #        temp2=-5, target2=[5,0,0,1], dot=5-5=0 >= 0 -> a = -5

        mock_arm._plane_eqn = np.array([1, 0, 0, -5])
        mock_arm.controller.absolute_position.return_value = {"A": 10, "B": 0, "C": 0}

        rel_vec = np.array([-1.0, 0.0, 0.0])
        d = 6.0
        speed = 500.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        mock_arm.controller.motor_a.relative_position.assert_called_once_with(-5)

    def test_target_below_plane_correction_on_idx1(self, mock_arm: MagicMock) -> None:
        """Target below chip plane, correction found on B axis (idx=1)."""
        # plane_eqn = [0, 1, 0, -5]: dot >= 0 means y >= 5
        # pos = {"A": 0, "B": 10, "C": 0}
        # rel_vec = [0, -1, 0], d = 6.0
        # a=0, b=-6, c=0, target=[0, 4, 0, 1], dot=4-5=-1 < 0
        # idx=0: temp1=-1, temp2=1
        #   target1=[-1,4,0,1], dot=4-5=-1 < 0
        #   target2=[1,4,0,1], dot=4-5=-1 < 0
        # idx=1: temp1=-7, temp2=-5
        #   target1=[0,3,0,1], dot=3-5=-2 < 0
        #   target2=[0,5,0,1], dot=5-5=0 >= 0 -> b = -5

        mock_arm._plane_eqn = np.array([0, 1, 0, -5])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 10, "C": 0}

        rel_vec = np.array([0.0, -1.0, 0.0])
        d = 6.0
        speed = 500.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        mock_arm.controller.motor_b.relative_position.assert_called_once_with(-5)

    def test_target_below_plane_correction_on_idx2(self, mock_arm: MagicMock) -> None:
        """Target below chip plane, correction found on C axis (idx=2)."""
        # plane_eqn = [0, 0, 1, 0]: z >= 0
        # pos = {"A": 0, "B": 0, "C": 0}
        # rel_vec = [0, 0, -1], d = 2.0
        # a=0, b=0, c=-2, target=[0,0,-2,1], dot=-2 < 0
        # idx=0: temp1=-1, temp2=1
        #   target1=[-1,0,-2,1], dot=-2 < 0
        #   target2=[1,0,-2,1], dot=-2 < 0
        # idx=1: temp1=-1, temp2=1
        #   target1=[0,-1,-2,1], dot=-2 < 0
        #   target2=[0,1,-2,1], dot=-2 < 0
        # idx=2: temp1=-3, temp2=-1
        #   target1=[0,0,-3,1], dot=-3 < 0
        #   target2=[0,0,-1,1], dot=-1 < 0
        # -> flag stays 1, raises RuntimeError
        # Need to find a case where idx=2 correction works.
        # Use c = -1 so temp2 = 0 works:
        # rel_vec = [0, 0, -1], d = 1.0
        # a=0, b=0, c=-1, target=[0,0,-1,1], dot=-1 < 0
        # idx=0: temp1=-1, temp2=1
        #   target1=[-1,0,-1,1], dot=-1 < 0
        #   target2=[1,0,-1,1], dot=-1 < 0
        # idx=1: temp1=-1, temp2=1
        #   target1=[0,-1,-1,1], dot=-1 < 0
        #   target2=[0,1,-1,1], dot=-1 < 0
        # idx=2: temp1=-2, temp2=0
        #   target1=[0,0,-2,1], dot=-2 < 0
        #   target2=[0,0,0,1], dot=0 >= 0 -> c = 0

        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}

        rel_vec = np.array([0.0, 0.0, -1.0])
        d = 1.0
        speed = 500.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        mock_arm.controller.motor_c.relative_position.assert_called_once_with(0)

    def test_target_below_plane_no_correction_raises_error(
        self, mock_arm: MagicMock
    ) -> None:
        """Target below chip plane with no possible ±1 correction raises RuntimeError."""
        # plane_eqn = [0, 0, 1, 0]: z >= 0
        # rel_vec = [0, 0, -1], d = 10.0
        # a=0, b=0, c=-10, target=[0,0,-10,1], dot=-10 < 0
        # All ±1 corrections on any axis still yield negative dot products.
        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}

        rel_vec = np.array([0.0, 0.0, -1.0])
        d = 10.0
        speed = 500.0

        with pytest.raises(RuntimeError, match="Cannot move to"):
            GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

    def test_speed_values_made_even(self, mock_arm: MagicMock) -> None:
        """If calculated speed is odd, it is incremented by 1 to become even."""
        # rel_vec = [1, 0, 0], speed = 7.0
        # sp_a = floor(1.0 * 7) = 7, odd -> 8
        # sp_b = floor(0 * 7) = 0, even -> 0
        # sp_c = floor(0 * 7) = 0, even -> 0
        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}

        rel_vec = np.array([1.0, 0.0, 0.0])
        d = 10.0
        speed = 7.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        mock_arm.controller.motor_a.speed.assert_called_once_with(8)
        mock_arm.controller.motor_b.speed.assert_called_once_with(0)
        mock_arm.controller.motor_c.speed.assert_called_once_with(0)

    def test_correct_acceleration_deceleration_values(
        self, mock_arm: MagicMock
    ) -> None:
        """Acceleration and deceleration values are computed via _calculate_vector_component."""
        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}
        mock_arm._acceleration = 2048
        mock_arm._deceleration = 4096

        rel_vec = np.array([1.0, 0.5, 0.0])
        d = 10.0
        speed = 100.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        expected_acc_a = _calculate_vector_component(vec=1.0, val=2048)
        expected_acc_b = _calculate_vector_component(vec=0.5, val=2048)
        expected_acc_c = _calculate_vector_component(vec=0.0, val=2048)
        expected_dec_a = _calculate_vector_component(vec=1.0, val=4096)
        expected_dec_b = _calculate_vector_component(vec=0.5, val=4096)
        expected_dec_c = _calculate_vector_component(vec=0.0, val=4096)

        mock_arm.controller.motor_a.acceleration.assert_called_once_with(expected_acc_a)
        mock_arm.controller.motor_b.acceleration.assert_called_once_with(expected_acc_b)
        mock_arm.controller.motor_c.acceleration.assert_called_once_with(expected_acc_c)
        mock_arm.controller.motor_a.deceleration.assert_called_once_with(expected_dec_a)
        mock_arm.controller.motor_b.deceleration.assert_called_once_with(expected_dec_b)
        mock_arm.controller.motor_c.deceleration.assert_called_once_with(expected_dec_c)

    def test_motor_methods_called_in_correct_order(self, mock_arm: MagicMock) -> None:
        """Each motor should have methods called in order:
        relative_position, speed, acceleration, deceleration, servo_here."""
        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {"A": 0, "B": 0, "C": 0}

        rel_vec = np.array([1.0, 0.5, 0.25])
        d = 10.0
        speed = 100.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        for motor in (
            mock_arm.controller.motor_a,
            mock_arm.controller.motor_b,
            mock_arm.controller.motor_c,
        ):
            method_names = [c[0] for c in motor.method_calls]
            assert method_names == [
                "relative_position",
                "speed",
                "acceleration",
                "deceleration",
                "servo_here",
            ]

    def test_with_nonzero_starting_position(self, mock_arm: MagicMock) -> None:
        """Target calculation accounts for current absolute position."""
        mock_arm._plane_eqn = np.array([0, 0, 1, 0])
        mock_arm.controller.absolute_position.return_value = {
            "A": 100,
            "B": 200,
            "C": 300,
        }

        rel_vec = np.array([0.5, 0.5, 0.5])
        d = 10.0
        speed = 100.0

        GalilDMC4133Arm._setup_motion(mock_arm, rel_vec, d, speed)

        # a = floor(0.5*10) = 5, b = 5, c = 5
        # target = [105, 205, 305, 1], dot([0,0,1,0], [105,205,305,1]) = 305 >= 0
        expected_target = np.array([105, 205, 305, 1])
        np.testing.assert_array_equal(mock_arm._target, expected_target)

        mock_arm.controller.motor_a.relative_position.assert_called_once_with(5)
        mock_arm.controller.motor_b.relative_position.assert_called_once_with(5)
        mock_arm.controller.motor_c.relative_position.assert_called_once_with(5)
