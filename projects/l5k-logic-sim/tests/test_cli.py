import os
from l5k_sim.__main__ import _resolve_web_dir


def test_web_dir_exists_and_has_index():
    web = _resolve_web_dir()
    assert os.path.isdir(web)
    assert os.path.isfile(os.path.join(web, "index.html"))
