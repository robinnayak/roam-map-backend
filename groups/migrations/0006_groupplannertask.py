from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0005_groupmembership_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupPlannerTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('category', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('done', 'Done')], default='todo', max_length=24)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_group_planner_tasks', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_group_planner_tasks', to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='planner_tasks', to='groups.group')),
            ],
            options={
                'ordering': ['category', 'sort_order', 'created_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='groupplannertask',
            index=models.Index(fields=['group', 'category', 'sort_order', 'created_at'], name='groups_grou_group_i_49f6c4_idx'),
        ),
        migrations.AddIndex(
            model_name='groupplannertask',
            index=models.Index(fields=['group', 'status'], name='groups_grou_group_i_e9f9a5_idx'),
        ),
        migrations.AddIndex(
            model_name='groupplannertask',
            index=models.Index(fields=['group', 'assigned_to'], name='groups_grou_group_i_8d6aa3_idx'),
        ),
    ]
