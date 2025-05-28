from odoo import fields,models,api


class MrpBom(models.Model):
    """ Defines bills of material for a product or a product template """
    _inherit = 'mrp.bom'

    is_standard = fields.Boolean()
    partner_id = fields.Many2one('res.partner',string="Customer")
    sale_order_number = fields.Char()
    sale_order_line_id = fields.Char()


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    qty_type = fields.Selection([('unit','Unit'),('width','Width'),('height','Height'),('width_height','Width & Height')],default='unit')
    extra_percentage = fields.Float(default=0)