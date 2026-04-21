from rest_framework import serializers
from .models import Category, Post
from django.contrib.auth import get_user_model

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class PostListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    author_name = serializers.CharField(source='author.email', read_only=True) # Will use email as name placeholder if they don't have separate names

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'category', 'author_name', 'image', 'excerpt', 'published_date']

class PostDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    author_name = serializers.CharField(source='author.email', read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'category', 'author_name', 'image', 'excerpt', 'content', 'published_date', 'created_at']
