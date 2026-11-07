from accelerator_rag.evidence_pack.needs import parse_needs


def test_exact_record_routes_to_row_lookup():
    question = {
        "base_id": "Q1",
        "query": "CAB-A-CN01柜（DEVXSW02）交换机的 45-48 端口在配置表中分配给哪个系统、哪个 VLAN？",
        "scope": {"mode": "global", "revision_ids": []},
    }
    needs = parse_needs(question)
    assert needs.route == "exact_record"
    kinds = {item.kind for item in needs.entities}
    assert {"cabinet", "device", "port"} <= kinds
    names = {item.name for item in needs.relations}
    assert {"value", "scope", "counterpart"} <= names
    assert "boundary" not in names


def test_enumeration_and_connection_route_cross_source():
    question = {
        "base_id": "Q2",
        "query": "CAB-A-CN01柜（CTLSW001）交换机在配置表中共划分了哪些端口块？请完整列出每个端口块的系统与网络分配。",
    }
    needs = parse_needs(question)
    assert needs.route == "cross_source"
    enumeration = needs.relation("enumeration")
    assert required(enumeration)
    assert needs.relation("counterpart") is not None


def required(relation):
    return bool(relation and relation.required)


def test_version_question_returns_version_relations_only():
    question = {
        "base_id": "Q3",
        "query": "界面甲在第一版与第二版中分别通过什么路径进入？",
        "scope": {"mode": "explicit_revisions", "revision_ids": ["r1", "r2"]},
    }
    needs = parse_needs(question)
    assert needs.route == "document_explanation"
    assert needs.version_pair == ("r1", "r2")
    names = {item.name for item in needs.relations}
    assert {"version_left", "version_right"} <= names
    assert "requirement" not in names
    assert "boundary" not in names


def test_verification_question_requires_roles_and_scope():
    question = {
        "base_id": "Q4",
        "query": "恒温机柜的“回读温度采集值”要求，是否由同一测量端点的测试覆盖？",
    }
    needs = parse_needs(question)
    assert needs.route == "cross_source"
    names = {item.name for item in needs.relations}
    assert {"requirement", "test_result", "test_scope", "boundary"} <= names


def test_boundary_not_required_for_simple_allocation():
    question = {
        "base_id": "Q5",
        "query": "CAB-B-CN09柜（DEVXSW08）的 21-48 端口在配置表中是什么用途？",
    }
    needs = parse_needs(question)
    assert needs.relation("boundary") is None


def test_three_edition_question_is_version_route():
    question = {
        "base_id": "Q7",
        "query": "定时设备状态灯语义在三版手册中是否一致？",
    }
    needs = parse_needs(question)
    assert needs.route == "document_explanation"
    assert needs.relation("version_left") is not None
    assert needs.relation("version_right") is not None


def test_same_wording_alone_does_not_force_cross_source():
    question = {
        "base_id": "Q8",
        "query": (
            "BC2-CN01柜（DEVSW001）的 E005 与 E006 终端相同，但用途不同；"
            "E006 的用途栏写的是什么？"
        ),
    }
    needs = parse_needs(question)
    assert needs.route == "exact_record"
    assert needs.comparison is True


def test_contract_comparison_cue_routes_cross_source():
    question = {
        "base_id": "Q9",
        "query": "CAB-A-CN01柜（DEVXSW02）与 CAB-B-CN09柜两者的端口分配对应关系是什么？",
    }
    needs = parse_needs(question)
    assert needs.route == "cross_source"


def test_cable_identifier_is_extracted():
    question = {
        "base_id": "Q6",
        "query": "CAB-A-CN01柜（CTLSW001）的 E001 电缆接在哪里、属于哪类网络？",
    }
    needs = parse_needs(question)
    kinds = {(item.kind, item.raw) for item in needs.entities}
    assert ("cable", "E001") in kinds
