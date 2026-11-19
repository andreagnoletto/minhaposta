from django.contrib import admin

from .models import ResultSnapshot, Ticket


@admin.register(ResultSnapshot)
class ResultSnapshotAdmin(admin.ModelAdmin):
    list_display = ("lottery", "contest", "fetched_at")
    list_filter = ("lottery",)
    search_fields = ("contest",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("user", "lottery", "contest", "numbers_label", "status", "hits", "payout", "created_at")
    list_filter = ("lottery", "status")
    search_fields = ("user__username", "contest")
