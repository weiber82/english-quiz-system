# Generated by Django 4.2.21 on 2025-05-20 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('options', models.JSONField()),
                ('answer', models.CharField(max_length=1)),
                ('topic', models.CharField(max_length=50)),
                ('is_gpt_generated', models.BooleanField(default=False)),
                ('created_dt', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
