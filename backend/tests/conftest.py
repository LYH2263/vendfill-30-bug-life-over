import os
import tempfile

# 必须在导入 app.* 之前：把数据库指到临时 sqlite，避免依赖 postgres
_fd, _path = tempfile.mkstemp(prefix="vendfill-test-", suffix=".db")
os.close(_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_path}")
