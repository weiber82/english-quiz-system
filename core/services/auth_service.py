from core.models import User

class AuthService:
    def register(self, username, password):
        if User.find_by_username(username):
            return False, "使用者已存在"
        User.create(username, password)
        return True, "註冊成功"

    def login(self, request, username, password):
        user = User.find_by_username(username)
        if user and user.password == password:
            request.session['user_id'] = user.id
            return True, "登入成功"
        return False, "帳號或密碼錯誤"

    def logout(self, request):
        request.session.flush()
