from odoo import fields,models,api
from odoo.exceptions import AccessError, UserError, ValidationError


class CustomerSource(models.Model):
    _name = 'customer.source'

    name = fields.Char(required=1)


class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    normal_partner = fields.Selection([('normal','Normal'),('partner','Partner')],required=1)
    min_quantity = fields.Float(required=1)

    @api.constrains('min_quantity')
    def check_if_min_quantity_more_zero(self):
        for rec in self:
            if not rec.min_quantity :
                raise ValidationError('Please add Minimum Quantity More Than Zero')


class Partner(models.Model):
    _inherit = 'res.partner'

    def _default_category(self):
        return self.env['res.partner.category'].browse(self._context.get('category_id'))

    category_id = fields.Many2many('res.partner.category', column1='partner_id',required=1,
                                   column2='category_id', string='Tags', default=_default_category)

    customer_source_id = fields.Many2one('customer.source', 'Source', index=True, ondelete='set null')

    @api.constrains('phone')
    def check_if_phone_is_dublicated(self):
        for rec in self:
            partners = self.env['res.partner'].search([('parent_id','=',False),('phone','=',rec.phone),('id','!=',rec.id)],limit=1)
            if partners:
                raise ValidationError('Please Check Customer/Vendor Phone Number , You Have Same for {}'.format(partners.name))

    @api.constrains('category_id')
    def check_if_tags_is_dublicated(self):
        for rec in self:
            count= len(rec.category_id)
            if not count or count > 1:
                pass
                # raise ValidationError('Please Select One Tag/Category')
