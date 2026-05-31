# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Canopus post-init: make one dashboard the start page for every user
# (including non-admins) and create a demo non-admin user to prove it.
#
# Runs after `superset init` + `superset load_examples`. Idempotent.
#
import logging
import os

from superset.app import create_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("canopus.postinit")

app = create_app()

with app.app_context():
    from superset import db, security_manager
    from superset.models.dashboard import Dashboard
    from superset.models.user_attributes import UserAttribute

    # 1. Pick the target dashboard: a configured slug, else the first published
    #    one, else the first dashboard that exists.
    slug = os.getenv("CANOPUS_WELCOME_DASHBOARD_SLUG", "").strip()
    dashboard = None
    if slug:
        dashboard = db.session.query(Dashboard).filter_by(slug=slug).first()
        if dashboard is None:
            log.warning("No dashboard with slug '%s'; falling back.", slug)
    if dashboard is None:
        dashboard = (
            db.session.query(Dashboard)
            .filter_by(published=True)
            .order_by(Dashboard.id)
            .first()
            or db.session.query(Dashboard).order_by(Dashboard.id).first()
        )

    if dashboard is None:
        log.warning("No dashboards found - skipping start-page setup.")
        raise SystemExit(0)

    # 2. Publish it so non-owners (non-admins) can open it.
    if not dashboard.published:
        dashboard.published = True
        db.session.commit()

    # 3. Let the Gamma role read dashboards and their underlying data.
    gamma = security_manager.find_role("Gamma")
    if gamma:
        perm = security_manager.find_permission_view_menu(
            "all_datasource_access", "all_datasource_access"
        )
        if perm and perm not in gamma.permissions:
            security_manager.add_permission_role(gamma, perm)
            db.session.commit()

    # 4. Create a demo non-admin user (Gamma) to verify the flow.
    if gamma and not security_manager.find_user(username="viewer"):
        security_manager.add_user(
            username="viewer",
            first_name="View",
            last_name="Only",
            email="viewer@canopus.local",
            role=gamma,
            password="viewer",  # noqa: S106 - demo credential
        )
        log.info("Created demo non-admin user 'viewer' / 'viewer'.")

    # 5. Set the welcome dashboard for every existing user. The welcome()
    #    handler renders this dashboard server-side (reusing dashboard access
    #    checks), so there is no extra redirect to /login.
    users = db.session.query(security_manager.user_model).all()
    for user in users:
        attr = (
            db.session.query(UserAttribute).filter_by(user_id=user.id).first()
        )
        if attr is None:
            db.session.add(
                UserAttribute(
                    user_id=user.id, welcome_dashboard_id=dashboard.id
                )
            )
        else:
            attr.welcome_dashboard_id = dashboard.id
    db.session.commit()

    log.info(
        "Start dashboard set to id=%s ('%s') for %d user(s).",
        dashboard.id,
        dashboard.dashboard_title,
        len(users),
    )
