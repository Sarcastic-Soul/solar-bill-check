import { Link } from "react-router";
import { useTranslation } from "react-i18next";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="wrap py-20">
      <p className="display text-[120px] font-bold leading-none">404</p>
      <h1 className="display mt-4 text-[36px] font-semibold">{t("notFound.title")}</h1>
      <Link to="/" className="btn btn-ink mt-8">
        {t("notFound.back")}
      </Link>
    </div>
  );
}
