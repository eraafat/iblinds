from odoo import fields,models,api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    width = fields.Float()
    height = fields.Float()
    total_quantity= fields.Integer()
