from types import SimpleNamespace

from nodeskclaw_rpa_engine.runtime.dry_run import is_dry_run, should_block_write


def test_is_dry_run_reads_config_camel():
    ctx = SimpleNamespace(config={"dryRun": True}, input={})
    assert is_dry_run(ctx) is True


def test_is_dry_run_default_false():
    ctx = SimpleNamespace(config={}, input={})
    assert is_dry_run(ctx) is False


def test_blocks_statement_generate_post():
    assert (
        should_block_write(
            "POST", "https://supplier.tiandy.com/api/reconciliation/create"
        )
        is True
    )


def test_allows_login_post():
    assert should_block_write("POST", "https://supplier.tiandy.com/api/login") is False


def test_allows_get():
    assert should_block_write("GET", "https://supplier.tiandy.com/api/receipts") is False


def test_invoice_upload_only_when_allowed():
    url = "https://supplier.tiandy.com/api/invoice/upload"
    assert should_block_write("POST", url, allow_upload=False) is True
    assert should_block_write("POST", url, allow_upload=True) is False
