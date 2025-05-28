from odoo import fields,models,api,_

from odoo.exceptions import UserError, ValidationError


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def button_post(self):
        # self._check_balance_end_real_same_as_computed()

        print(''' Move the bank statements from 'draft' to 'posted'. ''')
        if any(statement.state != 'open' for statement in self):
            raise UserError(_("Only new statements can be posted."))
        for line in self.line_ids:
            print(line.payment_ref)
            print(line.amount)
        total_entry_encoding = sum([line.amount for line in self.line_ids])
        balance_end = self.balance_start + self.total_entry_encoding
        difference = self.balance_end_real - self.balance_end
        print(total_entry_encoding,balance_end,difference)
        if difference != 0:
            raise ValidationError(_("ending balance must be equal to computed balance"))

        for statement in self:
            if not statement.name:
                statement._set_next_sequence()

        self.write({'state': 'posted'})
        lines_of_moves_to_post = self.line_ids.filtered(lambda line: line.move_id.state != 'posted')
        if lines_of_moves_to_post:
            lines_of_moves_to_post.move_id._post(soft=False)



class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    account_id = fields.Many2one('account.account')
    ref_line = fields.Char('Refrence')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 'Analytic Account', copy=True, readonly=False,
        help="Analytic account in which cost and revenue entries will take place for financial management of the manufacturing order.")

    def _synchronize_to_moves(self, changed_fields):
        ''' Update the account.move regarding the modified account.bank.statement.line.
        :param changed_fields: A list containing all modified fields on account.bank.statement.line.
        '''
        print('changed_fields')
        print(changed_fields)
        if self._context.get('skip_account_move_synchronization'):
            return

        if not any(field_name in changed_fields for field_name in (
            'payment_ref', 'amount', 'amount_currency','account_id',
            'foreign_currency_id', 'currency_id', 'partner_id',
        )):
            return

        for st_line in self.with_context(skip_account_move_synchronization=True):
            liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()
            company_currency = st_line.journal_id.company_id.currency_id
            journal_currency = st_line.journal_id.currency_id if st_line.journal_id.currency_id != company_currency else False

            line_vals_list = st_line._prepare_move_line_default_vals()
            line_ids_commands = [(1, liquidity_lines.id, line_vals_list[0])]

            if suspense_lines:
                line_ids_commands.append((1, suspense_lines.id, line_vals_list[1]))
            else:
                line_ids_commands.append((0, 0, line_vals_list[1]))

            for line in other_lines:
                line_ids_commands.append((2, line.id))

            st_line_vals = {
                'currency_id': (st_line.foreign_currency_id or journal_currency or company_currency).id,
                'line_ids': line_ids_commands,
            }
            if st_line.move_id.partner_id != st_line.partner_id:
                st_line_vals['partner_id'] = st_line.partner_id.id
            st_line.move_id.write(st_line_vals)


    @api.depends('journal_id', 'currency_id','account_id', 'amount', 'foreign_currency_id', 'amount_currency',
                 'move_id.to_check',
                 'move_id.line_ids.account_id', 'move_id.line_ids.amount_currency',
                 'move_id.line_ids.amount_residual_currency', 'move_id.line_ids.currency_id',
                 'move_id.line_ids.matched_debit_ids', 'move_id.line_ids.matched_credit_ids')
    def _compute_is_reconciled(self):
        ''' Compute the field indicating if the statement lines are already reconciled with something.
        This field is used for display purpose (e.g. display the 'cancel' button on the statement lines).
        Also computes the residual amount of the statement line.
        '''
        for st_line in self:
            liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()

            # Compute residual amount
            if st_line.to_check:
                st_line.amount_residual = -st_line.amount_currency if st_line.foreign_currency_id else -st_line.amount
            elif suspense_lines.account_id.reconcile:
                st_line.amount_residual = sum(suspense_lines.mapped('amount_residual_currency'))
            else:
                st_line.amount_residual = sum(suspense_lines.mapped('amount_currency'))

            # Compute is_reconciled
            if not st_line.id:
                # New record: The journal items are not yet there.
                st_line.is_reconciled = False
            elif suspense_lines:
                # In case of the statement line comes from an older version, it could have a residual amount of zero.
                st_line.is_reconciled = suspense_lines.currency_id.is_zero(st_line.amount_residual)
            elif st_line.currency_id.is_zero(st_line.amount):
                st_line.is_reconciled = True
            else:
                # The journal entry seems reconciled.
                st_line.is_reconciled = True

    @api.model
    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current account.bank.statement.line
        record.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        rec_account = self.partner_id.property_account_receivable_id
        pay_account = self.partner_id.property_account_payable_id
        if not counterpart_account_id:
            counterpart_account_id = self.account_id.id if self.account_id else rec_account.id

        if not counterpart_account_id:
            raise UserError(_(
                "You can't create a new statement line without a suspense account set on the %s journal."
            ) % self.journal_id.display_name)

        liquidity_line_vals = self._prepare_liquidity_move_line_vals()

        # Ensure the counterpart will have a balance exactly equals to the amount in journal currency.
        # This avoid some rounding issues when the currency rate between two currencies is not symmetrical.
        # E.g:
        # A.convert(amount_a, B) = amount_b
        # B.convert(amount_b, A) = amount_c != amount_a

        counterpart_vals = {
            'name': self.payment_ref,
            'account_id': counterpart_account_id,
            'analytic_account_id':self.analytic_account_id.id if self.analytic_account_id else False,
            'amount_residual': liquidity_line_vals['debit'] - liquidity_line_vals['credit'],
        }

        if self.foreign_currency_id and self.foreign_currency_id != self.company_currency_id:
            # Ensure the counterpart will have exactly the same amount in foreign currency as the amount set in the
            # statement line to avoid some rounding issues when making a currency conversion.

            counterpart_vals.update({
                'currency_id': self.foreign_currency_id.id,
                'amount_residual_currency': self.amount_currency,
            })
        elif liquidity_line_vals['currency_id']:
            # Ensure the counterpart will have a balance exactly equals to the amount in journal currency.
            # This avoid some rounding issues when the currency rate between two currencies is not symmetrical.
            # E.g:
            # A.convert(amount_a, B) = amount_b
            # B.convert(amount_b, A) = amount_c != amount_a

            counterpart_vals.update({
                'currency_id': liquidity_line_vals['currency_id'],
                'amount_residual_currency': liquidity_line_vals['amount_currency'],
            })

        counterpart_line_vals = self._prepare_counterpart_move_line_vals(counterpart_vals)
        return [liquidity_line_vals, counterpart_line_vals]


    @api.onchange('partner_id')
    def get_partner_account(self):
        if self.partner_id:
            rec_account = self.partner_id.property_account_receivable_id
            pay_account = self.partner_id.property_account_payable_id
            self.account_id = rec_account.id

    # @api.onchange()