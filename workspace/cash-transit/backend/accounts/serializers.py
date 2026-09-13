from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(read_only=True)
    position_display = serializers.CharField(source='get_position_display', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, default='')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'employee_no', 'name', 'role', 'role_display',
            'position', 'position_display', 'phone', 'id_card',
            'branch', 'branch_name', 'active_duty', 'is_staff',
        ]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
