"""Simple CLI flow for scraping product URLs with variant selection."""

from backend.scraper import scrape_product_sync


def run_cli():
    url = input("Enter product URL: ").strip()
    product = scrape_product_sync(url)

    print("\nProduct detected:")
    print(product.title or "Unknown product")

    if product.variants:
        print("\nVariants available:")
        options = []
        for group in product.variants:
            for option in group.get("options", []):
                options.append((group["name"], option))
        for idx, (_, option) in enumerate(options, start=1):
            print(f"{idx}. {option}")
        all_idx = len(options) + 1
        print(f"{all_idx}. All variants")

        choice = input("\nChoose option: ").strip()
        try:
            picked = int(choice)
        except ValueError:
            picked = all_idx

        if 1 <= picked <= len(options):
            name, value = options[picked - 1]
            print(f"\nSelected variant: {name} = {value}")
        else:
            print("\nSelected: All variants")

    print("\nNormalized product data:")
    print(product.to_dict())


if __name__ == "__main__":
    run_cli()
