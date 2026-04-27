import wtforms
from flask import session
from flask_login import current_user
from werkzeug.security import check_password_hash
from wtforms.validators import length, DataRequired, Regexp, Length, EqualTo, Email
from exts import DB, IS_POSTGRES
from models import User


def _ph():
    """返回参数占位符：PostgreSQL用 %s，SQLite用 ?"""
    return '%s' if IS_POSTGRES else '?'


class RegisterForm(wtforms.Form):
    username = wtforms.StringField(
        validators=[
            DataRequired(message='用户名不能为空'),
            Length(min=3, max=20, message='用户名长度需在3 - 20位之间'),
            Regexp(
                regex=r'^[a-zA-Z][a-zA-Z0-9]*$',
                message='用户名必须以字母开头，且只能包含字母和数字'
            )
        ]
    )
    password = wtforms.StringField(validators=[DataRequired(), Length(min=3, max=20, message='密码格式错误')])
    confirmPassword = wtforms.StringField(validators=[EqualTo('password', message='密码输入不一致')])

    def validate_password(self, field):
        if ' ' in field.data:
            raise wtforms.ValidationError('密码不能包含空格')

    def validate_username(self, field):
        if ' ' in field.data:
            raise wtforms.ValidationError('用户名不能包含空格')
        else:
            with DB() as cursor:
                ph = _ph()
                cursor.execute(f"SELECT name FROM users WHERE name = {ph}", (field.data,))
                user_name = cursor.fetchone()
                if user_name:
                    raise wtforms.ValidationError(f"{user_name['name']} 用户已注册！")


class LoginForm(wtforms.Form):
    username = wtforms.StringField(validators=[DataRequired(), Length(min=3, max=20, message='用户名格式错误')])
    password = wtforms.StringField(validators=[DataRequired(), Length(min=3, max=20, message='密码格式错误')])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def validate_username(self, field):
        try:
            with DB() as cursor:
                ph = _ph()
                query = f"""
                        SELECT id, name, created_at, updated_at, email, password, expire, cellphone, role, node, route, enable
                        FROM users
                        WHERE name = {ph}
                        """
                cursor.execute(query, (field.data,))
                user_data = cursor.fetchone()
                if user_data:
                    user = User(*user_data)
                    self.user = user
                    input_password = self.password.data
                    if check_password_hash(user.password, input_password):
                        if user.enable == 0:
                            raise wtforms.ValidationError("用户已被禁用！")
                    else:
                        raise wtforms.ValidationError("密码错误！")
                else:
                    raise wtforms.ValidationError("用户不存在！")
                return True
        except wtforms.ValidationError:
            raise
        except Exception as e:
            print(f"查询失败: {e}")
            raise wtforms.ValidationError("登录查询失败")


class PasswdForm(wtforms.Form):
    password = wtforms.StringField(validators=[DataRequired(), Length(min=3, max=20, message='密码格式错误')])
    new_password = wtforms.StringField(validators=[DataRequired(), Length(min=3, max=20, message='密码格式错误')])
    confirmPassword = wtforms.StringField(validators=[EqualTo('new_password', message='密码输入不一致')])

    def validate_password(self, field):
        if not (check_password_hash(current_user.password, field.data)):
            raise wtforms.ValidationError("当前密码输入错误！")
