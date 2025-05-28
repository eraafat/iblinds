from odoo import fields, models, api, _


class MrpRequest(models.Model):
    _name = 'mrp.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(tracking=True)
    partner_id = fields.Many2one('res.partner', string="Customer", tracking=True)
    sales_order_number = fields.Char(tracking=True)
    delivery_date = fields.Date(tracking=True)

    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')], tracking=True,
                             default='draft')
    total_count = fields.Integer(compute='compute_total_count', store=True, tracking=True)
    order_line = fields.One2many('mrp.request.line', 'mrp_id')
    mrp_count = fields.Integer('compute_count_member')
    mrp_production_ids = fields.One2many('mrp.production', 'request_id')

    def confirm_all_orders(self):
        for line in self.mrp_production_ids:
            line.action_confirm()
            line.qty_producing = line.product_qty
            line._set_qty_producing()

    def button_mark_done(self):
        for line in self.mrp_production_ids:
            line.button_mark_done()
            if len(self.mrp_production_ids.filtered(lambda x: x.state != 'done')) == 0 :
                self.state='done'

    @api.model
    @api.onchange('total_count')
    @api.depends('total_count')
    def compute_count_member(self):
        for rec in self:
            oper = self.env['mrp.production'].search([('request_id', '=', self.id)])
            print("oper")
            print(oper)
            print(len(oper))
            rec.mrp_count = len(oper)

    def action_view_manufacturing_operation(self):
        self.ensure_one()
        self.compute_count_member()

        productions = self.env['mrp.production'].search([('request_id', '=', self.id)])
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_production_action")

        if not productions:
            return {'type': 'ir.actions.act_window_close'}

        if len(productions) == 1:
            action.update({
                'views': [(self.env.ref('mrp.mrp_production_form_view').id, 'form')],
                'res_id': productions.id,
            })
        else:
            tree_view = self.env.ref('mrp.mrp_production_tree_view')
            form_view = self.env.ref('mrp.mrp_production_form_view')
            action.update({
                'views': [(tree_view.id, 'list'), (form_view.id, 'form')],
                'domain': [('id', 'in', productions.ids)],
            })

        return action

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('mrp.request') or _('New')
        return super(MrpRequest, self).create(vals)

    @api.depends('order_line')
    def compute_total_count(self):
        for rec in self:
            total_count = 0
            for line in rec.order_line:
                total_count += line.count
            rec.total_count = total_count

    def create_mrp_operation(self):
        for line in self.order_line:
            values = {
                'request_line_id': line.id,
                'request_id': self.id,
                'product_id': line.product_id.id,
                'product_qty': line.count,
                'width': line.width, 'height': line.height,
                'bom_id': line.bom_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'partner_id': self.partner_id.id,
                'sales_order_number': self.sales_order_number,
                'origin': self.name,
            }
            print("values")
            print("values")
            print("values")
            print("values")
            print(values)
            mo = self.env['mrp.production'].create(values)
            # mo._onchange_picking_type()
            # mo._onchange_bom_id()
            mo.product_qty = line.count
            # mo._onchange_move_raw()
            # mo._onchange_move_finished()
            # mo._onchange_location()
            # mo._onchange_location_dest()
        self.compute_count_member()
        self.state = 'in_progress'

    draft_count = fields.Integer(compute='compute_draft_count')
    confirmed_count = fields.Integer(compute='compute_draft_count')

    def compute_draft_count(self):
        for rec in self:
            rec.draft_count = len(rec.mrp_production_ids.filtered(lambda x: x.state == 'draft'))
            rec.confirmed_count = len(rec.mrp_production_ids.filtered(lambda x: x.state in ['progress','to_close']))


class MrpRequestLine(models.Model):
    _name = 'mrp.request.line'

    product_id = fields.Many2one('product.product', required=True)
    color_id = fields.Many2one('product.product', required=True)
    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()
    send_to_mrp = fields.Boolean()
    mrp_state = fields.Selection([('draft', 'draft'), ('MRP', 'MRP')], default='draft')
    mrp_id = fields.Many2one('mrp.request')
    bom_count = fields.Integer(related='product_id.bom_count')
    sale_line_id = fields.Many2one('sale.order.line')
    bom_id = fields.Many2one('mrp.bom')


class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _inherit = 'mrp.production'

    height = fields.Float()
    width = fields.Float()
    partner_id = fields.Many2one('res.partner', string="Customer")
    sales_order_number = fields.Char()
    mrp_id = fields.Many2one('mrp.request')
    mrp_line_id = fields.Many2one('mrp.request.line')
    request_id = fields.Many2one('mrp.request')
    request_line_id = fields.Many2one('mrp.request.line')
