from django.shortcuts import render_to_response
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.contrib.auth.models import Group
from djangoacl.models import *
from django import forms
from django.forms import  widgets
from django.contrib import messages
from django.db.models import Q
from distutils.sysconfig import get_python_lib
import sys
from django.core.context_processors import csrf
import os.path
from django.db.utils import IntegrityError

class ACLModelAdmin(admin.ModelAdmin):
    """
    This class implements the ADMIN interface to the table we want to apply the ACL.
    """
    actions = ['delete_selected', 'change_permissions_action']
    if_nothing_allow = False
    save_on_top = True

    def get_actions(self, request):
        """
        This function overide the admin.ModelAdmin function, and replace the default delete action by our action
        """
        user = request.user
        if user.is_superuser: 
            return super(ACLModelAdmin, self).get_actions(request)

        actions = super(ACLModelAdmin, self).get_actions(request)
        values = actions['delete_selected']
        actions['delete_selected'] = values[0], values[1], ("Delete selected %s" % self.model._meta.verbose_name_plural)
        return actions

    def change_permissions_action(self, request, queryset):
        """
        Implements the change permissions action
        """
        user = request.user
        
        formclass = type( "ChangePermissionsForm", (forms.Form,), 
            dict( model = self.model.acl.through, 
                group = forms.ModelChoiceField(Group.objects, label="Group"),
                permissions = forms.BooleanField(label='Give permissions',required=False),
                read = forms.BooleanField(label='Read +',required=False),
                update = forms.BooleanField(label='Update +',required=False),
                delete = forms.BooleanField(label='Delete +',required=False),
                nread = forms.BooleanField(label='Read -',required=False),
                nupdate = forms.BooleanField(label='Update -',required=False),
                ndelete = forms.BooleanField(label='Delete -',required=False),
                _selected_action=forms.CharField(widget=forms.MultipleHiddenInput))
        )
        form = None

        
        if not user.is_superuser:
            groups = user.groups.all()
            before = queryset.count()
            tablename = (self.model.__name__).lower() 
            query_str = """Q(%sacl__acltable_permissions=True)&Q(acl__in=groups)""" % (tablename)
            query = eval(query_str) 
            queryset = queryset.filter(query).distinct()
            now = queryset.count()
            if now<before: 
                messages.warning(request, "Be aware that you are trying to change registers that you don't have permitions too!! Bellow you will see only the registers that you have permissions.")

        if 'apply' in request.POST:
            form = formclass(request.POST)
            if form.is_valid():
                group = form.cleaned_data['group']

                permissions = form.cleaned_data['permissions']

                read = form.cleaned_data['read']
                update = form.cleaned_data['update']
                delete = form.cleaned_data['delete']

                nread = form.cleaned_data['nread']
                nupdate = form.cleaned_data['nupdate']
                ndelete = form.cleaned_data['ndelete']

                for obj in queryset: obj.changePermissions(group,permissions,read,update,delete,nread,nupdate,ndelete)

                self.message_user(request, "Permissions where successfully changed")
                return HttpResponseRedirect(request.get_full_path())        
        
        items = queryset
        ids = []
        for item in items: ids.append( item.pk )
        
        

        if form==None: form = formclass(initial={'_selected_action': ids})

        data2template = { '_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME), 'ChangePermissionsForm': form, "items": items}
        data2template.update(csrf(request))
        return render_to_response( "admin/change_permissions.html", data2template)
    change_permissions_action.short_description = "Change permissions"
    
    def delete_selected(self, request, queryset):
        """
        Implements the delete action
        """
        user = request.user
        if user.is_superuser: return admin.actions.delete_selected(self,request, queryset)

        groups = user.groups.all()
        before = queryset.distinct().count()

        tablename = (self.model.__name__).lower() 
        query_str = """Q(%sacl__acltable_ndelete=False)&Q(%sacl__acltable_delete=True)&Q(acl__in=groups)""" % (tablename,tablename)
        query = eval(query_str)

        queryset = queryset.filter(query).distinct()
        now = queryset.count()
        if now<before: 
            messages.warning(request, "Be aware that you are trying to delete registers, that you don't have permitions too!! Bellow you will see only the registers that you have delete permissions.")
            
        return admin.actions.delete_selected(self,request, queryset)
    delete_selected.short_description = "Delete selected Items"
    
    def queryset(self, request):
        """
        This function overide the admin.ModelAdmin function.
        Filter the registers to be shown according to the user permissions
        """
        user = request.user
        if user.is_superuser: 
            return super(ACLModelAdmin, self).queryset(request)

        qs = super(ACLModelAdmin, self).queryset(request)
        groups = user.groups.all()
        
        tablename = (self.model.__name__).lower() 
        query_str = """Q(%sacl__acltable_nread=False)&(Q(%sacl__acltable_permissions=True)|
                    Q(%sacl__acltable_read=True)|Q(%sacl__acltable_update=True)|
                    Q(%sacl__acltable_delete=True))&Q(acl__in=groups)""" % (tablename,tablename,tablename,tablename,tablename)
        query = eval(query_str)
        
        qs = qs.filter(query).distinct()
        return qs

    """
    def has_change_permission(self, request, obj=None):
        #This function overide the admin.ModelAdmin function.
        #Check if the user can see the permissions form in the Table Form
        
        user = request.user
        if user.is_superuser: 
            class_name = "%sACLAdminInline" % self.model.__name__
            found = False
            if hasattr( self,  'inline_instances'):
                for instance in self.inline_instances:
                    if instance.__class__.__name__==class_name: 
                        found = True
                        break
                if not found:
                    tabclass = type( class_name, (admin.TabularInline,), dict( model = self.model.acl.through, extra=0) )
                    inline_instance = tabclass(self.model, self.admin_site)
                    self.inline_instances.append(inline_instance)
            return super(ACLModelAdmin, self).has_change_permission(request, obj)

        groups = user.groups.all()

        if obj!=None:         
            
            tablename = (self.model.__name__).lower() 
            query_str = 'Q(%sacl__foreign=%d)&Q(%sacl__acltable_permissions=True)&Q(acl__in=groups)' % (tablename,obj.pk,tablename)
            query = eval(query_str)

            res = self.model.objects.filter(query)
            if res.count()>0: 
                found = False
                class_name = "%sACLAdminInline" % self.model.__name__
                if not hasattr(self,'inline_instances'): self.inline_instances = []

                for instance in self.inline_instances:
                    print instance
                    if instance.__class__.__name__==class_name: 
                        found = True
                        break

                if not found:
                    tabclass = type( class_name, (admin.TabularInline,), dict( model = self.model.acl.through, extra=0) )
                    inline_instance = tabclass(self.model, self.admin_site)
                    self.inline_instances.append(inline_instance)
            else:
                class_name = "%sACLAdminInline" % self.model.__name__
                for instance in self.inline_instances:
                    if instance.__class__.__name__==class_name: 
                        self.inline_instances.remove(instance)
        
        return super(ACLModelAdmin, self).has_change_permission( request, obj)
    """

    def get_inline_instances(self, request, obj=None):
        user = request.user
        if user.is_superuser: 
            class_name = "%sACLAdminInline" % self.model.__name__
            found = False
            if hasattr( self,  'inlines'):
                for instance in self.inlines:
                    if instance.__name__==class_name: 
                        found = True
                        break
                if not found:
                    tabclass = type( class_name, (admin.TabularInline,), dict( model = self.model.acl.through, extra=0, suit_classes='suit-tab suit-tab-acls') )
                    self.inlines.append(tabclass)
            return super(ACLModelAdmin, self).get_inline_instances(request, obj)

        groups = user.groups.all()

        if obj!=None:         
            
            tablename = (self.model.__name__).lower() 
            query_str = """Q(%sacl__foreign=%d)&Q(%sacl__acltable_permissions=True)&Q(acl__in=groups)""" % (tablename,obj.pk,tablename)
            query = eval(query_str)

            res = self.model.objects.filter(query)
            if res.count()>0: 
                found = False
                class_name = "%sACLAdminInline" % self.model.__name__
               
                for instance in self.inlines:
                    if instance.__name__==class_name: 
                        found = True
                        break

                if not found:
                    tabclass = type( class_name, (admin.TabularInline,), dict( model = self.model.acl.through, extra=0, suit_classes='suit-tab suit-tab-acls') )
                    self.inlines.append(tabclass)
            else:
                class_name = "%sACLAdminInline" % self.model.__name__
                for instance in self.inlines:
                    if instance.__class__.__name__==class_name: 
                        self.inlines.remove(instance)
        return super(ACLModelAdmin, self).get_inline_instances(request, obj)
    
    def has_add_permission(self, request):
        perm = super(ACLModelAdmin, self).has_add_permission(request)
        user = request.user
        if user.is_superuser: return perm

        if perm:
            groups = request.user.groups.all()
            tablename = (self.model.__name__).lower() 
            query_str = """Q(applyto__in=groups)&Q(acltemplate_table__model='%sacl')""" % tablename
            query = eval(query_str)            
            res = ACLTemplate.objects.filter(query)
            if res.count()==0:
                messages.warning(request, "You need entries in acltemplate table to be able to create new items.")
                return False
            else:
                return True
        else:
            return False

    def has_delete_permission(self, request, obj=None):
        """
        This function overide the admin.ModelAdmin function.
        Check if the user can delete the register in the Table Form
        """
        user = request.user
        if user.is_superuser: 
            return super(ACLModelAdmin, self).has_delete_permission(request, obj)

        if obj==None: return True
        groups = user.groups.all()
        
        tablename = (self.model.__name__).lower() 
        query_str = """Q(%sacl__foreign=%d)&Q(%sacl__acltable_ndelete=True)&Q(acl__in=groups)""" % (tablename,obj.pk,tablename)
        query = eval(query_str)

        res = self.model.objects.filter(query)
        if res.count()>0: return False
        
        query_str = """Q(%sacl__foreign=%d)&Q(%sacl__acltable_delete=True)&Q(acl__in=groups)""" % (tablename,obj.pk,tablename)
        query = eval(query_str)

        res = self.model.objects.filter(query)
        if res.count()>0: return True
        return False


    def save_model(self, request, obj, form, change):
        """
        This function overide the admin.ModelAdmin function.
        Check if the user can update the register in the Table Form
        """

        user = request.user
        if user.is_superuser: return super(ACLModelAdmin, self).save_model(request, obj, form, change)

        groups = user.groups.all()
        tablename = (self.model.__name__).lower()

        if change:
            warning_msg = "You don't have permissions to update this register."

            allow = False

            query_str = """Q(%sacl__foreign=%d)&Q(%sacl__acltable_permissions=True)&Q(acl__in=groups)""" % (tablename,obj.pk,tablename)
            query = eval(query_str)            
            res = self.model.objects.filter(query)
            
            if res.count()>0: allow = True
            
            if not allow:
                query_str = """Q(%sacl__foreign=%d)&Q(%sacl__acltable_permissions=False)&Q(%sacl__acltable_nupdate=True)&Q(acl__in=groups)""" % (tablename,obj.pk,tablename,tablename)
                query = eval(query_str)            
                res = self.model.objects.filter(query)

                if res.count()>0: 
                    allow = False
                else:
                    query_str = """Q(%sacl__foreign=%d)&(Q(%sacl__acltable_update=True)|Q(%sacl__acltable_permissions=True))&Q(acl__in=groups)""" % (tablename,obj.pk,tablename,tablename)
                    query = eval(query_str)   
                    res = self.model.objects.filter(query)
                    if res.count()>0: allow = True
            
            if allow:
                return super(ACLModelAdmin, self).save_model(request, obj, form, change)
            else:
                messages.warning(request, warning_msg)
                
        elif obj.pk==None:          
            
            super(ACLModelAdmin, self).save_model(request, obj, form, change)            
            query_str = """Q(acltemplate_table__model='%sacl')&Q(applyto__in=groups)""" % tablename
            query = eval(query_str)   
            rows = ACLTemplate.objects.filter(query).distinct()
            for row in rows:
                aclrow = obj.acl.through()
                aclrow.acltable_permissions = row.acltemplate_permissions
                aclrow.acltable_read = row.acltemplate_read
                aclrow.acltable_update = row.acltemplate_update
                aclrow.acltable_delete = row.acltemplate_delete
                aclrow.acltable_nread = row.acltemplate_nread
                aclrow.acltable_nupdate = row.acltemplate_nupdate
                aclrow.acltable_ndelete = row.acltemplate_ndelete
                aclrow.group = row.group
                aclrow.foreign = obj
                try:  aclrow.save()
                except IntegrityError:  pass

            
                

class ACLTableAdminModel(admin.ModelAdmin):
    """
    This function overides the admin.ModelAdmin function.
    Check if the user can update the register in the Table Form
    """
    list_filter = ['group','acltable_permissions','acltable_read', 'acltable_update', 'acltable_delete','acltable_nread','acltable_nupdate','acltable_ndelete']
    list_display = ('foreign','acltable_permissions','acltable_read', 'acltable_update', 'acltable_delete','acltable_nread','acltable_nupdate','acltable_ndelete','group',)
    fieldsets = [
        (None, { 'fields': [('foreign','group','acltable_permissions','acltable_read', 'acltable_update', 'acltable_delete','acltable_nread','acltable_nupdate','acltable_ndelete'),] } )
    ]


class ACLTemplateAdminModel(admin.ModelAdmin):
    """
    This function overides the admin.ModelAdmin function.
    Check if the user can update the register in the Table Form
    """
    list_filter = ['acltemplate_table', 'group','acltemplate_permissions','acltemplate_read', 'acltemplate_update', 'acltemplate_delete','acltemplate_nread','acltemplate_nupdate','acltemplate_ndelete', 'applyto']
    list_display = ('acltemplate_table', 'group','acltemplate_permissions','acltemplate_read', 'acltemplate_update', 'acltemplate_delete','acltemplate_nread','acltemplate_nupdate','acltemplate_ndelete', 'applyto')
    fieldsets = [
        (None, { 'fields': [('acltemplate_table','group', 'applyto','acltemplate_permissions','acltemplate_read', 'acltemplate_update', 'acltemplate_delete','acltemplate_nread','acltemplate_nupdate','acltemplate_ndelete'),] } )
    ]


admin.site.register(ACLTemplate, ACLTemplateAdminModel)

