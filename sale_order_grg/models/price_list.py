from odoo import fields,models,api
from odoo.exceptions import ValidationError

class product_pricelist_inherit(models.Model):
    _inherit = "product.pricelist"


    price = fields.Float()
    product_template = fields.Many2many('product.template')

    def update_products_prices_template(self):
        if not self.price or not self.product_template:
            raise ValidationError("please add product template and price")
        for line in self.item_ids.filtered(lambda p: p.product_tmpl_id.id in self.product_template.ids):
            print('updates---')
            line.fixed_price = self.price


    def get_all_products_template(self):
        product_tems = self.env['product.template'].search([('is_fabric','=',True)])
        for product in product_tems:
            self.item_ids = [(0, 0, {
            'product_id': variant.id,
            'product_tmpl_id': product.id,
        }) for variant in self.env['product.product'].search([('product_tmpl_id','=',product.id)])]

    # 'line_ids': [(0, 0, {
    #     'account_id': acc_template_ref[line.account_id].id,
    #     'label': line.label,
    #     'amount_type': line.amount_type,
    #     'force_tax_included': line.force_tax_included,
    #     'amount_string': line.amount_string,
    #     'tax_ids': [[4, tax_template_ref[tax].id, 0] for tax in line.tax_ids],
    # }) for line in account_reconcile_model_lines],
    # }


