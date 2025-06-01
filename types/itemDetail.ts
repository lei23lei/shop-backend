export interface ItemDetail {
  id: number;
  name: string;
  price: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  categories: {
    id: number;
    name: string;
  }[];
  details: {
    color: string;
    detail: string | null;
  } | null;
  sizes: {
    size: string;
    quantity: number;
  }[];
  images: {
    id: number;
    image_url: string;
    is_primary: boolean;
  }[];
  detail_images: {
    id: number;
    image_url: string;
    display_order: number;
  }[];
}
