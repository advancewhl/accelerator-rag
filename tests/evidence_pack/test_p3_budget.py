from accelerator_rag.evidence_pack.budget import MAX_TOKENS, policy_for


def test_route_budgets(needs_factory):
    exact = policy_for(needs_factory(route="exact_record", relations=()))
    explain = policy_for(
        needs_factory(route="document_explanation", relations=())
    )
    cross = policy_for(needs_factory(route="cross_source", relations=()))
    assert exact.tokens == 1200
    assert explain.tokens == 2400
    assert cross.tokens == 3600
    assert exact.max_rounds == 1
    assert explain.max_rounds == 2


def test_optional_relations_do_not_add_budget(needs_factory):
    optional = (
        __import__(
            "accelerator_rag.evidence_pack.schema", fromlist=["RelationNeed"]
        ).RelationNeed("enumeration", False, "可选"),
    )
    policy = policy_for(
        needs_factory(route="document_explanation", relations=optional)
    )
    assert policy.tokens == 2400


def test_relation_surcharge_and_cap(needs_factory):
    relations = tuple(
        __import__(
            "accelerator_rag.evidence_pack.schema", fromlist=["RelationNeed"]
        ).RelationNeed(name, True, "test")
        for name in ("value", "unit", "condition", "counterpart", "scope")
    )
    policy = policy_for(needs_factory(route="cross_source", relations=relations))
    assert policy.tokens == 3600 + 2 * 150
    many = tuple(
        __import__(
            "accelerator_rag.evidence_pack.schema", fromlist=["RelationNeed"]
        ).RelationNeed(name, True, "test")
        for name in (
            "value",
            "unit",
            "condition",
            "counterpart",
            "scope",
            "boundary",
            "enumeration",
            "requirement",
            "test_result",
            "test_scope",
            "acceptance",
            "design",
        )
    )
    assert policy_for(needs_factory(route="cross_source", relations=many)).tokens == 4950
    assert policy_for(needs_factory(route="cross_source", relations=many)).tokens <= MAX_TOKENS
