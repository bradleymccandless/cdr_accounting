from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Rate, CDR
import json

class RateAdmin(admin.ModelAdmin):
    list_display = ('accountcode', 'local_calling_area', 'pulse', 'channels', 'inbound_rate', 'inbound_tollfree_rate', 'outbound_rate', 'canadian_ld_rate', 'united_states_ld_rate', 'international_ld_rate')
class CDRAdmin(admin.ModelAdmin):
    list_display = ('starting_date', 'switch', 'caller_id_name_pretty', 'caller_id_number', 'destination_number', 'channel', 'duration', 'hangup_cause_id', 'direction', 'accountcode', 'extradata_pretty')
    list_display_links = None
    search_fields = ('starting_date', 'caller_id_name', 'caller_id_number', 'destination_number', 'channel', 'duration', 'hangup_cause_id', 'extradata')
    readonly_fields = ('starting_date', 'switch', 'caller_id_name', 'destination_number', 'channel', 'duration', 'hangup_cause_id', 'direction', 'extradata')
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super(CDRAdmin, self).has_change_permission(request, obj=obj)
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def get_actions(self, request):
        actions = super(CDRAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    def extradata_pretty(self, instance):
        response = {k: v for k, v in instance.extradata.items() if v}
        response = json.dumps(response, sort_keys=True, indent=2).strip().replace('{','').replace('}','').replace('\"','').replace(',\n',', ')
        return mark_safe(response)
    def caller_id_name_pretty(self, instance):
        if '\"' in instance.caller_id_name:
            return mark_safe(instance.caller_id_name.split('"')[1])
        return mark_safe(instance.caller_id_name)
    extradata_pretty.short_description = 'Extras'
    caller_id_name_pretty.short_description = 'Caller ID Name'
admin.site.register(Rate, RateAdmin)
admin.site.register(CDR, CDRAdmin)