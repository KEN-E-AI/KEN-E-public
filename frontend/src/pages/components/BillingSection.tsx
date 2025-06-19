import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CreditCard, FileText, Calendar, Download } from "lucide-react";
import { type Organization } from "@/data/organizationData";

interface BillingSectionProps {
  orgData: Organization;
}

const BillingSection = ({ orgData }: BillingSectionProps) => {
  const mockInvoices = [
    {
      date: "Jan 15, 2024",
      amount: "$99.00",
      status: "Paid",
      invoice: "INV-2024-001",
    },
    {
      date: "Dec 15, 2023",
      amount: "$99.00",
      status: "Paid",
      invoice: "INV-2023-012",
    },
    {
      date: "Nov 15, 2023",
      amount: "$99.00",
      status: "Paid",
      invoice: "INV-2023-011",
    },
  ];

  return (
    <>
      {/* Billing Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Billing Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <Label className="mr-auto">Payment Method</Label>
                <p className="text-sm text-dashboard-gray-600">
                  •••• •••• •••• {orgData.billing.payment_method.last_four} (
                  {orgData.billing.payment_method.brand}) - Expires{" "}
                  {orgData.billing.payment_method.expires}
                </p>
              </div>
              <Button variant="outline" size="sm">
                Update Payment
              </Button>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <Label className="mr-auto">Billing Address</Label>
                <p className="text-sm text-dashboard-gray-600">
                  {orgData.billing.address}
                </p>
              </div>
              <Button variant="outline" size="sm">
                Update Address
              </Button>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <Label className="mr-auto">Tax Information</Label>
                <p className="text-sm text-dashboard-gray-600">
                  VAT ID: {orgData.billing.tax_id}
                </p>
              </div>
              <Button variant="outline" size="sm">
                Update Tax Info
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Billing History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Billing History
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            {mockInvoices.map((invoice, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 border rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Calendar className="h-4 w-4 text-dashboard-gray-400" />
                  <div>
                    <p className="font-medium">{invoice.invoice}</p>
                    <p className="text-sm text-dashboard-gray-600">
                      {invoice.date}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="font-medium">{invoice.amount}</p>
                    <Badge
                      variant="secondary"
                      className="bg-green-100 text-green-800"
                    >
                      {invoice.status}
                    </Badge>
                  </div>
                  <Button variant="ghost" size="sm">
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-center pt-4">
            <Button variant="outline">View All Invoices</Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
};

export default BillingSection;
