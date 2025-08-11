from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    reference = fields.Char()


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_category_id = fields.Many2one('res.partner.category', compute='get_partner_category_from_customer',
                                          store=True,
                                          string='Partner tags')
    vat_invoice_number = fields.Char()
    reviewer_employee_id = fields.Many2one('hr.employee',string="Reviewer")
    collector_employee_id = fields.Many2one('hr.employee',string="Collector")
    materials = fields.Many2many('product.product',compute='get_colors_from_lines')
    materials_name = fields.Char(compute='get_colors_from_lines')

    @api.depends('invoice_line_ids','invoice_line_ids.color_id')
    def get_colors_from_lines(self):
        for rec in self:
            material = ''
            print('1')
            print(rec.materials)
            for line in rec.invoice_line_ids:
                if line.color_id:
                    print('if')
                    print(rec.materials)
                    rec.materials = [(4,line.color_id.id)]
                    material += line.color_id.display_name +  ', '
                else:
                    print('else')
                    print(rec.materials)
                    rec.materials = rec.materials if rec.materials else False
            print('l')
            print(rec.materials)
            if not rec.materials:
                rec.materials = False
            else:
                rec.materials = rec.materials
            rec.materials_name = material if material else '--'


    def action_update_line_receivable(self):
        for rec in self:
            for line in rec.line_ids:
                if line.account_id.user_type_id.id == 1:
                    line.name = 'Order Number ' + (rec.invoice_origin if rec.invoice_origin else '- ') + ', total count = ' + str(rec.total_counts )+ ', total quantity = ' + str(rec.total_quantity)

    def action_post(self):
        if self.total_quantity and self.total_counts and self.invoice_origin:
            self.action_update_line_receivable()
        return super(AccountMove, self).action_post()

    @api.depends('partner_id', 'partner_id.category_id')
    def get_partner_category_from_customer(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.category_id:
                rec.partner_category_id = rec.partner_id.category_id[0]
            else:
                rec.partner_category_id = False

    total_price_materials = fields.Monetary(
        string="Material Price",
        compute='calculate_count_of_lines',
        store=True
    )
    total_taxed_price_materials = fields.Monetary(
        string="Material Taxed Price",
        compute='calculate_count_of_lines',
        store=True
    )
    total_counts = fields.Integer(
        compute='calculate_count_of_lines',
        store=True
    )
    total_quantity = fields.Float(
        compute='calculate_count_of_lines',
        store=True
    )

    @api.depends(
        'invoice_line_ids.count',
        'invoice_line_ids.quantity',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.price_total',
        'invoice_line_ids.width',
        'invoice_line_ids.height',
        'invoice_line_ids.color_id'
    )
    def calculate_count_of_lines(self):
        for rec in self:
            if rec.move_type in ['out_invoice', 'in_invoice']:
                total_count = 0
                total_quantity = 0
                total_price = 0
                total_taxed = 0
                for line in rec.invoice_line_ids:
                    if line.count and line.width and line.height and line.color_id:
                        total_count += line.count
                        total_quantity += line.quantity
                        total_price += line.price_subtotal
                        total_taxed += line.price_total
                rec.total_counts = total_count
                rec.total_quantity = total_quantity
                rec.total_price_materials = total_price
                rec.total_taxed_price_materials = total_taxed
            else:
                rec.total_counts = 0
                rec.total_quantity = 0
                rec.total_price_materials = 0
                rec.total_taxed_price_materials = 0


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()
    color_id = fields.Many2one('product.product', domain=[('is_fabric', '=', True)])

    @api.onchange('height', 'width')
    def onchange_eight_width(self):
        print("iam in height and width")
        if self.width and self.height:
            self.quantity = self.width * self.height
