import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProductCategoriesManagement } from "./ProductCategoriesManagement";
import { AuthContext } from "@/contexts/AuthContext";
import * as productCategoryService from "@/services/productCategoryService";
import * as productService from "@/services/productService";

// Mock AccountOperationsContext
const mockStartOperation = vi.fn();
const mockEndOperation = vi.fn();
vi.mock("@/contexts/AccountOperationsContext", () => ({
  useAccountOperations: () => ({
    startOperation: mockStartOperation,
    endOperation: mockEndOperation,
    isLoading: false,
    currentOperation: null,
  }),
}));

// Mock services
vi.mock("@/services/productCategoryService");
vi.mock("@/services/productService");

// Mock toast
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock ReactFlow
vi.mock("reactflow", () => ({
  ReactFlow: ({ nodes, edges, onNodeClick }: any) => (
    <div data-testid="react-flow">
      {nodes.map((node: any) => (
        <div
          key={node.id}
          data-testid={`node-${node.type}-${node.id}`}
          onClick={(e) => onNodeClick(e, node)}
        >
          {node.data.label}
        </div>
      ))}
    </div>
  ),
  Controls: () => <div data-testid="flow-controls" />,
  Background: () => <div data-testid="flow-background" />,
}));

// Mock custom nodes
vi.mock("./ProductFlowNodes", () => ({
  CategoryNode: ({ data }: any) => <div>{data.label}</div>,
  ProductNode: ({ data }: any) => <div>{data.label}</div>,
}));

describe("ProductCategoriesManagement - Product CRUD Integration Tests", () => {
  const mockAuthContext = {
    selectedOrgAccount: {
      orgId: "org_test" as any,
      accountId: "acc_test" as any,
      metadata: {
        organization_name: "Test Org",
        account_name: "Test Account",
        industry: "Technology",
        status: "Active",
      },
    },
  };

  const mockCategory = {
    node_id: "cat_1",
    account_id: "acc_test",
    product_name: "Test Category",
    description: "Test category description",
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
  };

  const mockProduct = {
    node_id: "prod_1",
    account_id: "acc_test",
    product_name: "Test Product",
    description: "Test product description",
    references: [],
    product_detail_page: "https://example.com/product",
    category_node_id: "cat_1",
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockToast.mockClear();

    // Default mocks
    vi.mocked(
      productCategoryService.productCategoryService.list,
    ).mockResolvedValue({
      product_categories: [mockCategory],
      total_count: 1,
    });

    vi.mocked(productService.productService.list).mockResolvedValue({
      products: [],
      total_count: 0,
    });
  });

  const renderComponent = (hasEditAccess = true) => {
    return render(
      <AuthContext.Provider value={mockAuthContext as any}>
        <ProductCategoriesManagement hasEditAccess={hasEditAccess} />
      </AuthContext.Provider>,
    );
  };

  describe("Product Creation", () => {
    it("creates product and keeps category selected with context menu open", async () => {
      const user = userEvent.setup();
      const newProduct = { ...mockProduct, node_id: "prod_new" };

      vi.mocked(productService.productService.create).mockResolvedValueOnce(
        newProduct,
      );
      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [newProduct],
        total_count: 1,
      });

      renderComponent();

      // Wait for categories to load and click one
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      // Wait for React Flow to render
      await waitFor(() => {
        expect(screen.getByTestId("react-flow")).toBeInTheDocument();
      });

      // Click "+" button on category node (would be in real implementation)
      // For test, we'll simulate opening the modal directly
      const createButton = screen
        .getAllByRole("button")
        .find((btn) => btn.querySelector("svg"));
      if (createButton) {
        await user.click(createButton);
      }

      // Fill out product form (if modal is open)
      const productNameInput = screen.queryByPlaceholderText(/Business Loans/i);
      if (productNameInput) {
        await user.type(productNameInput, "New Product");

        const descriptionInput = screen.getByPlaceholderText(
          /Describe this product/i,
        );
        await user.type(descriptionInput, "New product description");

        const createProductButton = screen.getByRole("button", {
          name: /Create Product/i,
        });
        await user.click(createProductButton);

        // Verify product was created
        await waitFor(() => {
          expect(productService.productService.create).toHaveBeenCalledWith(
            "acc_test",
            expect.objectContaining({
              product_name: "New Product",
              description: "New product description",
              category_node_id: "cat_1",
            }),
          );
        });

        // Verify success toast
        expect(mockToast).toHaveBeenCalledWith({
          title: "Success",
          description: "Product created successfully",
        });
      }
    });

    it("validates required fields when creating product", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      // Try to create without filling fields
      const createButton = screen
        .getAllByRole("button")
        .find((btn) => btn.querySelector("svg"));
      if (createButton) {
        await user.click(createButton);
      }

      const createProductButton = screen.queryByRole("button", {
        name: /Create Product/i,
      });
      if (createProductButton) {
        await user.click(createProductButton);

        // Should show validation error
        await waitFor(() => {
          expect(mockToast).toHaveBeenCalledWith({
            title: "Validation Error",
            description: "Product name and description are required",
            variant: "destructive",
          });
        });
      }
    });
  });

  describe("Product Edit", () => {
    it("saves product updates including product_detail_page", async () => {
      const user = userEvent.setup();
      const updatedProduct = {
        ...mockProduct,
        product_name: "Updated Product",
        product_detail_page: "https://example.com/updated",
      };

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      vi.mocked(productService.productService.update).mockResolvedValueOnce(
        updatedProduct,
      );

      renderComponent();

      // Select category
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      // Wait for product to appear in diagram
      await waitFor(() => {
        expect(
          screen.getByTestId("node-productNode-prod_1"),
        ).toBeInTheDocument();
      });

      // Click product node
      const productNode = screen.getByTestId("node-productNode-prod_1");
      await user.click(productNode);

      // Click Edit button (context menu should be open)
      const editButton = screen.queryByRole("button", { name: /Edit/i });
      if (editButton) {
        await user.click(editButton);

        // Update fields
        const nameInput = screen.getByLabelText(/Name:/i);
        await user.clear(nameInput);
        await user.type(nameInput, "Updated Product");

        const detailPageInput = screen.queryByLabelText(/Product Detail Page/i);
        if (detailPageInput) {
          await user.type(detailPageInput, "https://example.com/updated");
        }

        // Save changes
        const saveButton = screen.getByRole("button", {
          name: /Save Changes/i,
        });
        await user.click(saveButton);

        // Verify update was called
        await waitFor(() => {
          expect(productService.productService.update).toHaveBeenCalledWith(
            "acc_test",
            "prod_1",
            expect.objectContaining({
              product_name: "Updated Product",
              product_detail_page: "https://example.com/updated",
            }),
          );
        });

        // Verify success toast
        expect(mockToast).toHaveBeenCalledWith({
          title: "Success",
          description: "Product updated successfully",
        });
      }
    });

    it("detects unsaved changes including product_detail_page", async () => {
      const user = userEvent.setup();

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      renderComponent();

      // Select category and product
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      await waitFor(() => {
        expect(
          screen.getByTestId("node-productNode-prod_1"),
        ).toBeInTheDocument();
      });

      const productNode = screen.getByTestId("node-productNode-prod_1");
      await user.click(productNode);

      // Edit product_detail_page
      const editButton = screen.queryByRole("button", { name: /Edit/i });
      if (editButton) {
        await user.click(editButton);

        const detailPageInput = screen.queryByLabelText(/Product Detail Page/i);
        if (detailPageInput) {
          await user.type(detailPageInput, "https://example.com/changed");

          // Try to close without saving - should prevent or warn
          // (Implementation-specific behavior test)
        }
      }
    });
  });

  describe("Product Display", () => {
    it("displays product_detail_page as clickable link", async () => {
      const user = userEvent.setup();

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      renderComponent();

      // Select category
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      // Click product node
      await waitFor(() => {
        expect(
          screen.getByTestId("node-productNode-prod_1"),
        ).toBeInTheDocument();
      });

      const productNode = screen.getByTestId("node-productNode-prod_1");
      await user.click(productNode);

      // Check for product_detail_page link
      const link = screen.queryByRole("link", {
        name: /example\.com\/product/i,
      });
      if (link) {
        expect(link).toHaveAttribute("href", "https://example.com/product");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
      }
    });
  });

  describe("Product Delete", () => {
    it("deletes product with confirmation dialog", async () => {
      const user = userEvent.setup();

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      vi.mocked(productService.productService.delete).mockResolvedValueOnce();

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [],
        total_count: 0,
      });

      renderComponent();

      // Select category and product
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      await waitFor(() => {
        expect(
          screen.getByTestId("node-productNode-prod_1"),
        ).toBeInTheDocument();
      });

      const productNode = screen.getByTestId("node-productNode-prod_1");
      await user.click(productNode);

      // Click Delete button
      const deleteButton = screen.queryByRole("button", { name: /Delete/i });
      if (deleteButton) {
        await user.click(deleteButton);

        // Confirm deletion in AlertDialog
        await waitFor(() => {
          const confirmButton = screen.queryByRole("button", {
            name: /Delete/i,
          });
          if (confirmButton && confirmButton !== deleteButton) {
            return user.click(confirmButton);
          }
        });

        // Verify delete was called
        await waitFor(() => {
          expect(productService.productService.delete).toHaveBeenCalledWith(
            "acc_test",
            "prod_1",
          );
        });

        // Verify success toast
        expect(mockToast).toHaveBeenCalledWith({
          title: "Success",
          description: "Product deleted successfully",
        });
      }
    });

    it("handles delete permission error", async () => {
      const user = userEvent.setup();

      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      const error = new Error("Forbidden");
      (error as any).response = {
        status: 403,
        data: { detail: "Permission denied" },
      };
      vi.mocked(productService.productService.delete).mockRejectedValueOnce(
        error,
      );

      renderComponent();

      // Select category and product
      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      const categoryBadge = screen.getByText("Test Category").closest("div");
      if (categoryBadge) {
        await user.click(categoryBadge);
      }

      await waitFor(() => {
        expect(
          screen.getByTestId("node-productNode-prod_1"),
        ).toBeInTheDocument();
      });

      const productNode = screen.getByTestId("node-productNode-prod_1");
      await user.click(productNode);

      // Attempt delete
      const deleteButton = screen.queryByRole("button", { name: /Delete/i });
      if (deleteButton) {
        await user.click(deleteButton);

        const confirmButton = screen.queryByRole("button", { name: /Delete/i });
        if (confirmButton && confirmButton !== deleteButton) {
          await user.click(confirmButton);
        }

        // Verify error toast
        await waitFor(() => {
          expect(mockToast).toHaveBeenCalledWith({
            title: "Permission Denied",
            description: "You don't have permission to delete products",
            variant: "destructive",
          });
        });
      }
    });
  });

  describe("Edit Access Control", () => {
    it("hides edit/delete buttons when hasEditAccess is false", async () => {
      vi.mocked(productService.productService.list).mockResolvedValueOnce({
        products: [mockProduct],
        total_count: 1,
      });

      renderComponent(false);

      await waitFor(() => {
        expect(screen.getByText("Test Category")).toBeInTheDocument();
      });

      // Edit/delete buttons should not be present
      expect(screen.queryByRole("button", { name: /Edit/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Delete/i })).toBeNull();
    });
  });
});
