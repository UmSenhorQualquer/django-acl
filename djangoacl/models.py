from django.contrib.auth.models import User, Group
from django.db import models
from django.contrib.contenttypes.models import ContentType

################################################################################
################################################################################
######################## CNP Common tables #####################################
################################################################################
################################################################################

class ACLTable(models.Model):
	"""
	This model implements the ACL and store the permissions of the Table registers.
	"""
	acltable_id         = models.AutoField('Id', primary_key=True)
	acltable_permissions= models.BooleanField('Give permissions')
	acltable_read       = models.BooleanField('Read +')
	acltable_update     = models.BooleanField('Update +')
	acltable_delete 	= models.BooleanField('Delete +')
	acltable_nread 		= models.BooleanField('Read -')
	acltable_nupdate 	= models.BooleanField('Update -')
	acltable_ndelete 	= models.BooleanField('Delete -')
	
	group 				= models.ForeignKey(Group)

	class Meta:
		abstract = True
		unique_together = (("group", "foreign"),)

	def delete(self):
		objects = self.__class__.objects.filter(foreign=self.foreign).filter(acltable_ndelete=True).filter(acltable_permissions=True)

		if self not in objects: 
			super(ACLTable, self).delete()

	def save(self, *args, **kwargs):
		objects = self.__class__.objects.filter(foreign=self.foreign).filter(acltable_read=True).filter(acltable_permissions=True)
		
		if self not in objects: 
			super(ACLTable, self).save(*args, **kwargs)
		elif self.acltable_permissions==True and self.acltable_read==True  and self.acltable_nread==False:
			super(ACLTable, self).save(*args, **kwargs)

		super(ACLTable, self).save(*args, **kwargs)

	def __unicode__(self):
		return "Group: %s: Permissions: %d|%d,%d,%d|%d,%d,%d" % (self.group, self.acltable_permissions, self.acltable_read, self.acltable_update, self.acltable_delete, self.acltable_nread, self.acltable_nupdate, self.acltable_ndelete)


	
class ACLTemplate(models.Model):
	"""
	This model store the permissions template to the tables
	"""
	acltemplate_id = models.AutoField('Id', primary_key=True)
	acltemplate_table = models.ForeignKey(ContentType, limit_choices_to={'model__endswith': 'acl'} )
	acltemplate_permissions = models.BooleanField('Give permissions')
	acltemplate_read = models.BooleanField('Read +')
	acltemplate_update = models.BooleanField('Update +')
	acltemplate_delete = models.BooleanField('Delete +')
	acltemplate_nread = models.BooleanField('Read -')
	acltemplate_nupdate = models.BooleanField('Update -')
	acltemplate_ndelete = models.BooleanField('Delete -')

	group = models.ForeignKey(Group, related_name='group+')
	applyto = models.ForeignKey(Group, related_name='applyto+', verbose_name='Permissions applied to')

	class Meta:
		unique_together = (("group", "applyto",'acltemplate_table'),)

	def __unicode__(self):
		return "Table: %s, Group: %s: Permissions: %d|%d,%d,%d|%d,%d,%d" % (self.acltemplate_table, self.group, self.acltemplate_permissions, self.acltemplate_read, self.acltemplate_update, self.acltemplate_delete, self.acltemplate_nread, self.acltemplate_nupdate, self.acltemplate_ndelete)


class ACLModel(models.Model):
	"""
	This model implements the ACL in the TableModel.
	"""
	def changePermissions(self,group, permissions=None,read=None,update=None,delete=None,nread=None,nupdate=None,ndelete=None):
		aclmodel =  self.acl.through
		acls = aclmodel.objects.filter( group=group, foreign=self.pk )
		print acls.query
		have = False

		for acl in acls:
			print acl
			have = True
			if permissions!=None:   acl.acltable_permissions = permissions
			if read!=None:          acl.acltable_read = read
			if update!=None:        acl.acltable_update = update
			if delete!=None:        acl.acltable_delete = delete
			if nread!=None:         acl.acltable_nread = nread
			if nupdate!=None:       acl.acltable_nupdate = nupdate
			if ndelete!=None:       acl.acltable_ndelete = ndelete
			acl.save()

		if not have:
			if permissions==None:   permissions = False
			if read==None:          read = False
			if update==None:        update = False
			if delete==None:        delete = False
			if nread==None:         nread = False
			if nupdate==None:       nupdate = False
			if ndelete==None:       ndelete = False
			acl = aclmodel(foreign=self,group=group, acltable_permissions=permissions,acltable_read=read,acltable_update=update,acltable_delete=delete,acltable_nread=nread,acltable_nupdate=nupdate,acltable_ndelete=ndelete)
			acl.save()
		
	class Meta:
		abstract = True
