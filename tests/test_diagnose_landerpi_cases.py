from rolo.stages.diagnose.landerpi_cases import (
    LanderPiDiagnoseCollector,
    LPD01Observation,
    LPD02Observation,
    LPD03Observation,
    evaluate_lp_d01,
    evaluate_lp_d02,
    evaluate_lp_d03,
)


def test_lp_d01_static_navigation_without_runtime_is_degraded() -> None:
    finding = evaluate_lp_d01(
        LPD01Observation(static_entrypoints=["/ws/src/navigation/launch/navigation.launch.py"])
    )
    assert finding.decision == "DEGRADED"
    assert finding.change == "NO_CHANGE"
    assert "controlled" in finding.next_probe


def test_lp_d01_runtime_action_is_healthy_but_limited() -> None:
    finding = evaluate_lp_d01(LPD01Observation(runtime_actions=["/navigate_to_pose"]))
    assert finding.decision == "HEALTHY"
    assert "physical safety" in finding.limitations[0]


def test_lp_d02_timeout_and_nan_is_degraded() -> None:
    finding = evaluate_lp_d02(
        LPD02Observation(
            sample_count=3,
            valid_range_count=7,
            total_range_count=10,
            nan_count=3,
            timeout_count=2,
            log_lines=["LD19 get ldlidar data is time out"],
        )
    )
    assert finding.decision == "DEGRADED"
    assert "timeout" in finding.smoke_result


def test_lp_d02_requires_a_window_not_one_sample() -> None:
    finding = evaluate_lp_d02(
        LPD02Observation(sample_count=1, valid_range_count=100, total_range_count=100)
    )
    assert finding.decision == "DEGRADED"
    assert "fewer than three samples" in finding.smoke_result


def test_lp_d03_blocks_global_navigation_without_pose() -> None:
    finding = evaluate_lp_d03(
        LPD03Observation(
            tf_frames=["/map", "/odom", "/base_footprint"],
            map_to_base_footprint_available=False,
            map_topic_present=True,
            map_publisher_count=1,
            localization_nodes=["/amcl"],
            localization_lifecycle={"/amcl": "INACTIVE"},
            initial_pose_observed=False,
        )
    )
    assert finding.decision == "BLOCKED"
    assert "initial pose" in finding.smoke_result


def test_lp_d03_ready_requires_all_global_prerequisites() -> None:
    finding = evaluate_lp_d03(
        LPD03Observation(
            tf_frames=["/map", "/odom", "/base_footprint"],
            map_to_base_footprint_available=True,
            map_topic_present=True,
            map_publisher_count=1,
            localization_nodes=["/amcl"],
            localization_lifecycle={"/amcl": "ACTIVE"},
            initial_pose_observed=True,
        )
    )
    assert finding.decision == "HEALTHY"


class _FakeTarget:
    workspace = "/home/ubuntu/ros2_ws"


class _FakeExecutor:
    target = _FakeTarget()

    def run_readonly(self, argv: list[str]):
        key = tuple(argv)
        outputs = {
            ("find", "/home/ubuntu/ros2_ws/src", "-maxdepth", "6", "-type", "f", "-iname", "*navigation*", "-print"):
                "/home/ubuntu/ros2_ws/src/navigation/launch/navigation.launch.py\n",
            ("find", "/home/ubuntu/ros2_ws/src", "-maxdepth", "6", "-type", "f", "-iname", "*nav2*", "-print"): "",
            ("find", "/home/ubuntu/ros2_ws/src", "-maxdepth", "6", "-type", "f", "-iname", "*map*.yaml", "-print"): "",
            ("ros2", "node", "list"): "/controller_server\n",
            ("ros2", "topic", "list"): "/scan\n",
            ("ros2", "action", "list"): "/navigate_to_pose\n",
            ("docker", "logs", "--tail", "200", "MentorPi"): "LD19 get ldlidar data is time out\n",
            ("ros2", "topic", "info", "/scan"): "Type: sensor_msgs/msg/LaserScan\nPublisher count: 1\n",
            ("timeout", "6", "ros2", "topic", "hz", "/scan", "--window", "5"): "average rate: 10.0\n",
            ("ros2", "topic", "echo", "--once", "/scan", "--field", "ranges"): "- 1.0\n- nan\n- 2.0\n",
        }
        from rolo.targets.executor import CommandResult

        return CommandResult(argv=key, returncode=0, stdout=outputs.get(key, ""))


def test_collector_uses_bounded_fixed_commands() -> None:
    collector = LanderPiDiagnoseCollector(_FakeExecutor())  # type: ignore[arg-type]
    d01 = collector.collect_lp_d01()
    d02 = collector.collect_lp_d02()
    assert evaluate_lp_d01(d01).decision == "HEALTHY"
    assert evaluate_lp_d02(d02).decision == "DEGRADED"
    assert d02.timeout_count == 1
