from django.contrib import admin
from .models import Order, Terminal, Robot, Program

admin.site.register(Order)
admin.site.register(Terminal)
admin.site.register(Robot)
admin.site.register(Program)
