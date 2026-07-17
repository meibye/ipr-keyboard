"""Unit tests for UserStore — credential storage and management."""
import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Fresh UserStore backed by a temporary users.json."""
    from ipr_keyboard.web import auth as auth_module

    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "users_path", lambda: users_file)
    monkeypatch.setattr(auth_module, "users_default_path", lambda: tmp_path / "users.default.json")
    monkeypatch.setattr(auth_module, "project_root", lambda: tmp_path)
    auth_module.UserStore._instance = None

    yield auth_module.UserStore.instance()

    auth_module.UserStore._instance = None


# ---------------------------------------------------------------------------
# Default user bootstrap
# ---------------------------------------------------------------------------


def test_default_admin_created_on_first_run(tmp_path, monkeypatch):
    """An admin user is created when users.json is empty or absent."""
    from ipr_keyboard.web import auth as auth_module

    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "users_path", lambda: users_file)
    monkeypatch.setattr(auth_module, "users_default_path", lambda: tmp_path / "users.default.json")
    monkeypatch.setattr(auth_module, "project_root", lambda: tmp_path)
    auth_module.UserStore._instance = None

    store = auth_module.UserStore.instance()
    assert store.user_exists("admin")
    auth_module.UserStore._instance = None


def test_initial_password_file_written(tmp_path, monkeypatch):
    """The random initial password is written to admin_initial_password.txt."""
    from ipr_keyboard.web import auth as auth_module

    monkeypatch.setattr(auth_module, "users_path", lambda: tmp_path / "users.json")
    monkeypatch.setattr(auth_module, "users_default_path", lambda: tmp_path / "users.default.json")
    monkeypatch.setattr(auth_module, "project_root", lambda: tmp_path)
    auth_module.UserStore._instance = None

    auth_module.UserStore.instance()

    pwd_file = tmp_path / "admin_initial_password.txt"
    assert pwd_file.exists()
    initial_pwd = pwd_file.read_text().strip()
    assert len(initial_pwd) >= 16
    auth_module.UserStore._instance = None


def test_initial_password_allows_login(tmp_path, monkeypatch):
    """The password written to file lets the admin log in immediately."""
    from ipr_keyboard.web import auth as auth_module

    monkeypatch.setattr(auth_module, "users_path", lambda: tmp_path / "users.json")
    monkeypatch.setattr(auth_module, "users_default_path", lambda: tmp_path / "users.default.json")
    monkeypatch.setattr(auth_module, "project_root", lambda: tmp_path)
    auth_module.UserStore._instance = None

    store = auth_module.UserStore.instance()
    initial_pwd = (tmp_path / "admin_initial_password.txt").read_text().strip()
    assert store.verify("admin", initial_pwd) is True
    auth_module.UserStore._instance = None


def test_default_admin_is_admin(store):
    """The auto-created admin account has is_admin=True."""
    info = store.user_info("admin")
    assert info["is_admin"] is True


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------


def test_verify_correct_credentials(store):
    store.add_user("alice", "securepassword1", is_admin=False)
    assert store.verify("alice", "securepassword1") is True


def test_verify_wrong_password(store):
    store.add_user("alice", "securepassword1", is_admin=False)
    assert store.verify("alice", "wrongpassword") is False


def test_verify_unknown_user(store):
    assert store.verify("nobody", "anything") is False


# ---------------------------------------------------------------------------
# add_user()
# ---------------------------------------------------------------------------


def test_add_user_creates_entry(store):
    store.add_user("bob", "password123", is_admin=False)
    assert store.user_exists("bob")


def test_add_user_can_login_immediately(store):
    store.add_user("bob", "password123", is_admin=False)
    assert store.verify("bob", "password123") is True


def test_add_user_duplicate_raises(store):
    store.add_user("bob", "password123")
    with pytest.raises(ValueError, match="already exists"):
        store.add_user("bob", "anotherpassword")


def test_add_user_invalid_username_raises(store):
    with pytest.raises(ValueError, match="Username must be"):
        store.add_user("A B", "password123")


def test_add_user_username_too_short_raises(store):
    with pytest.raises(ValueError, match="Username must be"):
        store.add_user("ab", "password123")


def test_add_user_short_password_raises(store):
    with pytest.raises(ValueError, match="Password must be at least"):
        store.add_user("charlie", "short")


def test_add_user_admin_flag_stored(store):
    store.add_user("adminuser", "password123", is_admin=True)
    info = store.user_info("adminuser")
    assert info["is_admin"] is True


# ---------------------------------------------------------------------------
# user_info() and list_users()
# ---------------------------------------------------------------------------


def test_user_info_returns_metadata(store):
    store.add_user("alice", "password123", is_admin=False)
    info = store.user_info("alice")
    assert info["username"] == "alice"
    assert info["is_admin"] is False
    assert "created_at" in info


def test_user_info_unknown_user_raises(store):
    with pytest.raises(KeyError):
        store.user_info("nobody")


def test_list_users_includes_all(store):
    store.add_user("alice", "password123")
    store.add_user("bob", "password456")
    names = {u["username"] for u in store.list_users()}
    assert {"admin", "alice", "bob"}.issubset(names)


# ---------------------------------------------------------------------------
# change_password()
# ---------------------------------------------------------------------------


def test_change_password_new_password_works(store):
    store.add_user("alice", "oldpassword1")
    store.change_password("alice", "newpassword1")
    assert store.verify("alice", "newpassword1") is True


def test_change_password_old_password_rejected(store):
    store.add_user("alice", "oldpassword1")
    store.change_password("alice", "newpassword1")
    assert store.verify("alice", "oldpassword1") is False


def test_change_password_short_raises(store):
    store.add_user("alice", "oldpassword1")
    with pytest.raises(ValueError, match="Password must be at least"):
        store.change_password("alice", "short")


def test_change_password_unknown_user_raises(store):
    with pytest.raises(KeyError):
        store.change_password("nobody", "newpassword1")


# ---------------------------------------------------------------------------
# set_admin()
# ---------------------------------------------------------------------------


def test_set_admin_promotes_user(store):
    store.add_user("alice", "password123", is_admin=False)
    store.set_admin("alice", True)
    assert store.user_info("alice")["is_admin"] is True


def test_set_admin_demotes_user(store):
    store.add_user("alice", "password123", is_admin=True)
    store.set_admin("alice", False)
    assert store.user_info("alice")["is_admin"] is False


def test_set_admin_cannot_remove_last_admin(store):
    with pytest.raises(ValueError, match="last admin"):
        store.set_admin("admin", False)


def test_set_admin_unknown_user_raises(store):
    with pytest.raises(KeyError):
        store.set_admin("nobody", True)


# ---------------------------------------------------------------------------
# delete_user()
# ---------------------------------------------------------------------------


def test_delete_user_removes_entry(store):
    store.add_user("alice", "password123")
    store.delete_user("alice")
    assert not store.user_exists("alice")


def test_delete_admin_raises(store):
    with pytest.raises(ValueError, match="cannot be deleted"):
        store.delete_user("admin")


def test_delete_last_admin_raises(store):
    store.add_user("alice", "password123", is_admin=True)
    store.set_admin("admin", False)
    with pytest.raises(ValueError, match="last admin"):
        store.delete_user("alice")


def test_delete_unknown_user_raises(store):
    with pytest.raises(KeyError):
        store.delete_user("nobody")


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------


def test_singleton_returns_same_instance(tmp_path, monkeypatch):
    from ipr_keyboard.web import auth as auth_module

    monkeypatch.setattr(auth_module, "users_path", lambda: tmp_path / "users.json")
    monkeypatch.setattr(auth_module, "users_default_path", lambda: tmp_path / "users.default.json")
    monkeypatch.setattr(auth_module, "project_root", lambda: tmp_path)
    auth_module.UserStore._instance = None

    a = auth_module.UserStore.instance()
    b = auth_module.UserStore.instance()
    assert a is b
    auth_module.UserStore._instance = None
