from crm import create_app
app = create_app()
print('✓ App created successfully')
print('✓ Config JWT_ACCESS_TOKEN_EXPIRES:', app.config.get('JWT_ACCESS_TOKEN_EXPIRES'))
print('✓ Config CORS_ORIGINS:', app.config.get('CORS_ORIGINS'))
