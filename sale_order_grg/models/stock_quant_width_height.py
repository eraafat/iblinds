from odoo import fields, models, api


class StockQuantWidthHeight(models.Model):
    _name = 'stock.width.height'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    product_id = fields.Many2one('product.product')
    product_tmpl_id = fields.Many2one('product.template')
    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()
    stock_wh_line_ids = fields.One2many('stock.width.height.line','stock_wh_id')


class StockQuantWidthHeightLine(models.Model):
    _name = 'stock.width.height.line'

    product_id = fields.Many2one('product.product')
    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()
    quant_type = fields.Selection([('in','IN'),('out','OUT')],default='in')
    stock_wh_id = fields.Many2one( 'stock.width.height')