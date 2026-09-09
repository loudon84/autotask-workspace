from app.integrations.imap_utf7 import decode_modified_utf7, encode_modified_utf7


def test_encode_decode_chinese_folder():
    name = "BOE-SRM一站式平台-验证码"
    encoded = encode_modified_utf7(name)
    assert "&" in encoded
    assert decode_modified_utf7(encoded) == name
